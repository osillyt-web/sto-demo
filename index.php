<?php
/**
 * Прокси на Python-сервер (server.py).
 *
 * Сайт на alwaysdata имеет тип PHP, а приложение написано на Python
 * (самостоятельный HTTP-сервер на stdlib). Этот файл принимает HTTP-запрос
 * и передаёт его локальному процессу на 127.0.0.1:8500, возвращая ответ
 * без изменений: статус, заголовки и тело.
 *
 * Если процесс не отвечает (например, после перезагрузки сервера),
 * он поднимается здесь же через shell_exec — сайт восстанавливается сам
 * при первом обращении, без ручных действий.
 */

const BACKEND_PORT = 8500;
const BACKEND_HOST = '127.0.0.1';

/** Проверить, слушает ли порт. */
function backend_alive(int $port): bool
{
    $fp = @fsockopen(BACKEND_HOST, $port, $errno, $errstr, 0.4);
    if ($fp) {
        fclose($fp);
        return true;
    }
    return false;
}

/** Поднять процесс, если он не запущен. */
function backend_start(string $base, int $port): bool
{
    if (!function_exists('shell_exec')) {
        return false;
    }
    @mkdir($base . '/data', 0755, true);
    $cmd = 'cd ' . escapeshellarg($base)
        . ' && PORT=' . $port
        . ' HOST=' . BACKEND_HOST
        . ' PYTHONUTF8=1 nohup python3 server.py > data/app.log 2>&1'
        . ' & echo $! > data/app.pid';
    @shell_exec($cmd);

    for ($i = 0; $i < 40; $i++) {
        usleep(150000);
        if (backend_alive($port)) {
            return true;
        }
    }
    return false;
}

$base = __DIR__;
$port = BACKEND_PORT;

if (!backend_alive($port)) {
    backend_start($base, $port);
}

$uri = $_SERVER['REQUEST_URI'] ?? '/';
if ($uri === '' || $uri[0] !== '/') {
    $uri = '/' . $uri;
}

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$body = file_get_contents('php://input');
if ($body === false) {
    $body = '';
}

// Заголовки клиента, которые нужно передать дальше.
$forward = [];
foreach ($_SERVER as $key => $value) {
    if (strpos($key, 'HTTP_') === 0) {
        $name = str_replace('_', '-', substr($key, 5));
        $lower = strtolower($name);
        // Host подменять нельзя: сервер строит ссылки по своему SITE_URL,
        // а Connection/Content-Length управляются самим клиентом curl.
        if (in_array($lower, ['connection', 'content-length', 'host', 'accept-encoding'], true)) {
            continue;
        }
        $forward[] = $name . ': ' . $value;
    }
}
if (!empty($_SERVER['CONTENT_TYPE'])) {
    $forward[] = 'Content-Type: ' . $_SERVER['CONTENT_TYPE'];
}
$forward[] = 'X-Forwarded-Proto: https';
if (!empty($_SERVER['REMOTE_ADDR'])) {
    $forward[] = 'X-Forwarded-For: ' . $_SERVER['REMOTE_ADDR'];
}

$responseHeaders = [];
$status = 502;

$ch = curl_init('http://' . BACKEND_HOST . ':' . $port . $uri);
curl_setopt_array($ch, [
    CURLOPT_CUSTOMREQUEST  => $method,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HEADERFUNCTION => function ($ch, $line) use (&$responseHeaders, &$status) {
        $trimmed = trim($line);
        if ($trimmed === '') {
            return strlen($line);
        }
        if (stripos($trimmed, 'HTTP/') === 0) {
            $parts = explode(' ', $trimmed);
            if (isset($parts[1])) {
                $status = (int) $parts[1];
            }
            return strlen($line);
        }
        $pos = strpos($trimmed, ':');
        if ($pos !== false) {
            $responseHeaders[] = [substr($trimmed, 0, $pos), trim(substr($trimmed, $pos + 1))];
        }
        return strlen($line);
    },
    CURLOPT_TIMEOUT        => 25,
    CURLOPT_CONNECTTIMEOUT => 5,
    CURLOPT_HTTPHEADER     => $forward,
]);

if ($method !== 'GET' && $method !== 'HEAD') {
    curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
}
if ($method === 'HEAD') {
    curl_setopt($ch, CURLOPT_NOBODY, true);
}

$payload = curl_exec($ch);
$curlError = curl_error($ch);
curl_close($ch);

if ($payload === false) {
    http_response_code(502);
    header('Content-Type: text/plain; charset=utf-8');
    echo "Сайт временно недоступен: внутренний сервер не ответил.\n";
    if ($curlError) {
        error_log('proxy error: ' . $curlError);
    }
    exit;
}

http_response_code($status);

$skip = ['transfer-encoding', 'connection', 'content-length', 'keep-alive'];
foreach ($responseHeaders as [$name, $value]) {
    if (in_array(strtolower($name), $skip, true)) {
        continue;
    }
    header($name . ': ' . $value, false);
}

header('Content-Length: ' . strlen($payload));
echo $payload;

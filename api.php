<?php
require_once 'db.php';
header('Content-Type: application/json');

$action = $_GET['action'] ?? '';
switch($action) {
    case 'documentos':
        // Implementar GET, POST, PUT, DELETE
        break;
    case 'upload':
        // Implementar POST para subir archivo
        break;
    case 'codigos':
        // Autocomplete/búsqueda
        break;
    case 'buscar':
        // Búsqueda voraz
        break;
    case 'consulta':
        // Consulta de documentos
        break;
    case 'login':
        // Login simple clave admin
        break;
    default:
        echo json_encode(["error" => "Acción no válida"]);
        exit;
}
?>

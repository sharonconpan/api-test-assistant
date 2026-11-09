# API Test Assistant

Herramienta inteligente para relacionar cambios en APIs REST con casos de prueba revisables, Pytest y CI/CD.

## Hito 1: API de ejemplo

El ejemplo implementa una API CRUD en memoria para elementos. Sus requisitos funcionales (RF) pertenecen al sistema bajo prueba (SUT) y se asignan explícitamente a las operaciones OpenAPI en `examples/sample_api/rf_map.yaml`:

| RF del SUT | Operación |
|---|---|
| RF01.1 — Crear elemento | `POST /items` |
| RF01.2 — Listar elementos | `GET /items` |
| RF01.3 — Consultar elemento | `GET /items/{item_id}` |
| RF01.4 — Actualizar elemento | `PUT /items/{item_id}` |
| RF01.5 — Eliminar elemento | `DELETE /items/{item_id}` |

El nombre debe contener entre 1 y 80 caracteres; la descripción es opcional y admite hasta 200 caracteres. La aplicación asigna IDs incrementales y conserva los elementos solo mientras vive el proceso.

La especificación que compara el detector se mantiene versionada en `examples/sample_api/openapi.json`. Después de cambiar la aplicación, actualízala desde la raíz del repositorio:

```powershell
python examples\sample_api\export_openapi.py
```

Revisa y versiona el JSON resultante junto con el cambio de la aplicación.

### Preparar el entorno en Windows PowerShell

Desde la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si PowerShell bloquea la activación del entorno, en esa terminal se puede ejecutar:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Ejecutar las pruebas

Con `.venv` activo:

```powershell
python -m pytest examples/sample_api/tests -v
```

Las pruebas usan `fastapi.testclient.TestClient` en proceso; no necesitan iniciar un servidor ni conectarse a un servicio externo.

## Hito 2: análisis de cambios Git y OpenAPI

El analizador usa `git` instalado en el sistema y no añade dependencias. Compara los archivos versionados y las operaciones OpenAPI en dos revisiones; relaciona una operación con cambios Python únicamente si el diff contiene evidencia de su ruta, `operationId` o esquema. Los cambios sin asociación demostrable se reportan separados como `solo_codigo` o `solo_openapi`.

Con `.venv` activo, configura el módulo y ejecuta el analizador desde la raíz del repositorio:

```powershell
$env:PYTHONPATH = (Join-Path $PWD 'src')
$base = "SHA_BASE"
$head = "SHA_DESTINO"
python -m api_test_assistant --repo . --base $base --head $head --spec examples/sample_api/openapi.json --output impacts.json
```

Reemplaza `SHA_BASE` y `SHA_DESTINO` por referencias Git resolubles a commits. `--repo` selecciona el repositorio y `--spec` es una ruta relativa versionada en ambas revisiones; se aceptan JSON y YAML. Si `--spec` se omite, usa la especificación del ejemplo. `--output` escribe JSON UTF-8 y puede omitirse para imprimir el JSON en pantalla. El campo `openapi.status` es `sin_cambios` cuando ambas especificaciones se analizaron y no difieren, `cambios` si se detectaron diferencias y `no_se_pudo_analizar` si falta o no es válida la especificación; en este último caso el comando termina con código distinto de cero.

El JSON incluye los cambios Git, las operaciones y esquemas OpenAPI añadidos, eliminados o modificados, y los impactos con evidencia por fuente. El comparador recursivo informa cambios en parámetros, cuerpos, restricciones y respuestas.

Ejecuta las pruebas del hito 2 con:

```powershell
python -m pytest tests\test_change_analysis.py examples\sample_api\tests -v
```

### Iniciar la API para exploración manual

Con `.venv` activo:

```powershell
python -m uvicorn examples.sample_api.app.main:app --reload
```

La documentación interactiva estará en `http://127.0.0.1:8000/docs` y OpenAPI en `http://127.0.0.1:8000/openapi.json`. Detén el servidor con `Ctrl+C`.

### Dependencias del hito

- `fastapi`: API y contrato OpenAPI.
- `pydantic`: validación de entradas y límites del contrato.
- `uvicorn`: servidor para exploración local.
- `httpx`: transporte usado por `TestClient`; Starlette aún lo admite, aunque versiones recientes emiten una advertencia de deprecación a favor de `httpx2`.
- `pytest`: ejecución de las pruebas.
- `PyYAML`: lectura y verificación del mapa RF del SUT.

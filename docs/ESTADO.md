# Estado del proyecto

Última actualización: 9 de noviembre de 2026.

## Hitos completados

- **Hito 1 — API de ejemplo:** API CRUD FastAPI en memoria, requisitos RF01.1–RF01.5 del sistema bajo prueba, mapa `rf_map.yaml`, snapshot OpenAPI y pruebas con `TestClient`.
- **Hito 2 — detector Git/OpenAPI:** clasificación de archivos en diffs reales, comparación de operaciones/parámetros/cuerpos/restricciones/respuestas/esquemas, correlación por evidencia y CLI JSON.
- **Hito 3 — generador de casos con Gemini:** cliente REST configurable, contexto OpenAPI/RF pertinente, validación del catálogo, persistencia JSON y cliente simulado en pruebas. La integración real está desactivada por defecto.
- La referencia correcta de la propuesta está versionada en `docs/referencia/NOTAS_APUNTES PARA RSL TAIS.md`.

## Preparación

Desde PowerShell en la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:PYTHONPATH = (Join-Path $PWD 'src')
```

Para ejecutar toda la suite del proyecto:

```powershell
python -m pytest tests examples\sample_api\tests -v
```

### Ejecutar la API de ejemplo y sus pruebas

```powershell
python -m pytest examples\sample_api\tests -v
python -m uvicorn examples.sample_api.app.main:app --reload
```

La aplicación expone `/docs` y `/openapi.json` en `http://127.0.0.1:8000`.

### Actualizar el snapshot OpenAPI

Después de modificar la aplicación de ejemplo:

```powershell
python examples\sample_api\export_openapi.py
```

Versiona `examples/sample_api/openapi.json` junto con el cambio de la aplicación.

### Analizar cambios Git y OpenAPI

```powershell
$base = "SHA_BASE"
$head = "SHA_DESTINO"
python -m api_test_assistant --repo . --base $base --head $head --spec examples/sample_api/openapi.json --output impacts.json
```

Reemplaza `SHA_BASE` y `SHA_DESTINO` por commits que contengan la especificación. El resultado `impacts.json` se genera localmente y contiene las revisiones, diffs de contrato y evidencia de impacto.

### Generar casos con Gemini

Configura la clave en el entorno o en `.env` local. No guardes una clave real en archivos versionados:

```powershell
Copy-Item .env.example .env
notepad .env
python -m api_test_assistant generate --impacts impacts.json --output cases.json
```

`GEMINI_MODEL` es opcional y por defecto usa `gemini-3.8-flash`. El archivo `cases.json` conserva el modelo, la fecha, los hashes y metadatos de uso disponibles, pero no la clave.

Prueba real opcional, desactivada por defecto:

```powershell
$env:RUN_GEMINI_INTEGRATION = "1"
python -m pytest tests\test_case_generation.py -k optional_real_gemini_integration -v
Remove-Item Env:RUN_GEMINI_INTEGRATION
```

## Decisiones tomadas

- API de ejemplo CRUD en memoria y FastAPI para obtener un contrato OpenAPI controlado.
- Los RF de los casos pertenecen al sistema bajo prueba y se asignan explícitamente con `rf_map.yaml`.
- Las pruebas de la API de ejemplo usan `TestClient` en proceso; no necesitan iniciar Uvicorn.
- El detector invoca Git mediante `subprocess`; el comparador usa un diff recursivo simple sobre JSON/YAML.
- Gemini se consume por HTTP con `httpx`, sin añadir SDK ni dependencia de cliente.
- Configuración por entorno o `.env`; el entorno prevalece y las claves nunca forman parte de prompts, casos o metadatos.
- Salida tabular como propiedades JSON con las nueve columnas del catálogo, cinco campos HTTP y decisión de revisión separada.
- Los casos nuevos empiezan como `No ejecutado`, `No` automatizados y `Pendiente`; solo Pytest podrá establecer su resultado.
- Hitos 1–3 completados en la rama de trabajo `feature/documentacion-inicial`; no se trabaja en `main`.

## Siguiente paso

Esperar aprobación del hito 3. Después, abordar el hito de revisión humana en tabla editable y exportación XLSX básica, manteniendo decisiones, estado de ejecución y automatización como campos separados.

# 03. Plan de hitos

## Reglas de ejecución

- El **hito 1** corresponde a esta entrega documental y consta de cuatro commits independientes, uno por documento.
- Al terminar el hito 1 se detendrá el trabajo y se esperará la aprobación explícita antes de crear o modificar código.
- Cada hito de implementación tendrá pruebas propias, actualización de `README.md` y comandos exactos de ejecución en Windows PowerShell con `.venv` activo.
- En cada hito se añadirá a `requirements.txt` únicamente una dependencia necesaria, con justificación.
- Antes de pasar al siguiente hito se validará el cambio y se creará un commit independiente en la rama de trabajo, con un mensaje claro de la forma `hito N: descripción`.
- La aprobación de una propuesta, la automatización y el resultado de ejecución se mantendrán como datos separados; el Estado solo cambiará con evidencia de Pytest.

## Hitos

| Hito | Entregable | Criterio de terminado |
|---:|---|---|
| 1. Documentación inicial | Requisitos, arquitectura, plan de hitos y diseño del pipeline CI. | Los cuatro documentos están en `docs/`, se revisaron contra la propuesta, no se añadió código, cada archivo tiene su commit `hito 1: ...` y se espera aprobación antes de programar. |
| 2. API de ejemplo y base de pruebas | API pequeña con FastAPI en `examples/`, contrato OpenAPI y configuración mínima de pruebas. | La API se inicia localmente, su contrato puede obtenerse y sus pruebas propias verifican operaciones, validación y al menos un límite. `README.md` documenta instalación y comandos PowerShell con `.venv` activo. Las dependencias añadidas son mínimas. |
| 3. Detector Git y analizador OpenAPI | Lectura reproducible de diffs entre revisiones, extracción y comparación de especificaciones. | Pruebas unitarias e integración cubren archivos añadidos, modificados, eliminados, errores y diferencias de contrato; la salida identifica operaciones y restricciones con evidencia y distingue la ausencia de cambios de errores de análisis. El README incluye comandos exactos de ejecución. |
| 4. Correlación de impactos | Unión de hallazgos de código y de contrato por evidencia y asociaciones explícitas. | Pruebas verifican impactos concordantes, solo código, solo OpenAPI, falta de contrato y asociaciones inciertas; los resultados no afirman relaciones sin evidencia. Se actualiza README y se documentan los comandos PowerShell. |
| 5. Generador de casos con Gemini | Cliente LLM configurable, validación estructurada y persistencia de casos candidatos según el catálogo. | Pruebas sin llamadas reales a Gemini verifican esquema, técnicas permitidas, formato de ID, campos HTTP y manejo de respuestas/errores; prueba de integración opcional requiere credencial local y no se ejecuta en la suite por defecto. Los casos nacen como pendientes, no ejecutados y no automatizados. README documenta configuración segura y comandos. |
| 6. Revisión humana y Excel | Interfaz web tabular editable, decisión por caso y exportación XLSX/JSON/CSV. | Pruebas comprueban edición, aprobación/rechazo, separación entre decisión y Estado, orden de columnas, hojas resumen y métricas por RF/módulo. Solo se exporta información definida; no se incluyen secretos. README describe los comandos PowerShell para iniciar la interfaz, probar y exportar. |
| 7. Generador de Pytest | Conversión de casos aprobados en pruebas inspeccionables. | Pruebas demuestran que solo los aprobados producen pruebas, que ID y RF son trazables y que datos inválidos no generan código. Casos pendientes y rechazados no se ejecutan. README actualiza flujo y comandos PowerShell. |
| 8. Ejecutor y resultados reales | Ejecución Pytest y asociación del resultado a cada caso. | Pruebas verifican actualización a Exitoso/Fallido solo con resultado real, No ejecutado para casos no corridos y manejo separado de errores de infraestructura. Se documentan ejecución local, reportes y comandos exactos en PowerShell. |
| 9. Pipeline GitHub Actions | Workflow Linux para `push` y `pull_request`, ejecución, reporte y publicación de artefactos. | Se valida sintaxis y comportamiento del workflow; los jobs ejecutan pruebas, publican reportes y fallan ante resultados fallidos. Secrets tienen mínimo alcance y no se exponen a Pull Requests no confiables. README documenta configuración y ejecución local equivalente. |
| 10. Reportes y métricas de evaluación | Reportes por RF/módulo y resultados del protocolo de evaluación. | Pruebas verifican denominadores, estados, distribución por técnica y métricas de calidad; la evaluación registra corrección, defectos detectados, cobertura, negativos, límites, cambios humanos y esfuerzo. Se reportan muestras y limitaciones, sin atribuir estados al LLM. README describe reproducción en Windows PowerShell. |
| 11. Integración extremo a extremo y documentación final | Flujo completo usando la API del ejemplo, pruebas de aceptación y guía de uso. | Una prueba de extremo a extremo recorre selección de cambios, impacto, caso revisado, Pytest, ejecución y reporte; se verifica la trazabilidad RF → CP → archivo. Documentación y comandos de PowerShell permiten repetir el flujo desde un entorno limpio. |

## Orden y justificación

La secuencia conserva el orden funcional propuesto: análisis Git/OpenAPI antes de Gemini; generación antes de revisión; revisión antes de Pytest; y ejecución antes del pipeline y las métricas. Se agregan dos pasos previos/de apoyo:

1. **API de ejemplo antes del detector:** proporciona un contrato y una aplicación controlados, propios del repositorio, que sirven como fixture de integración y permiten probar la herramienta sin depender de servicios externos.
2. **Correlación como hito separado:** dividir la extracción de diffs de su correlación hace que la atribución de impacto tenga pruebas específicas y pueda evidenciar con claridad incertidumbre y casos sin correspondencia.

El ejecutor se adelanta al pipeline para validar localmente la semántica real de Estado antes de automatizarla en CI. Los reportes básicos de ejecución se incluyen con el ejecutor; el hito de reportes posterior se concentra en agregaciones y métricas de investigación.

## Cierre y control de avance

Cada hito se considerará terminado cuando cumpla todos sus criterios, sus pruebas aplicables pasen, `README.md` incluya instrucciones reproducibles en PowerShell con `.venv` activo y el cambio quede registrado en un commit de la rama de trabajo. Si un hito descubre una decisión que afecte alcance o formato, se detendrá esa parte y se consultará antes de asumir una extensión.

Al completar el hito 1, se presentará un resumen de los cuatro documentos. La aprobación recibida para redactarlos no autoriza automáticamente a comenzar el hito 2 ni ningún cambio de código; se esperará la aprobación expresa para continuar.

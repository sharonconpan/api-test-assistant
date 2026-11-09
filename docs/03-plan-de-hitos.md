# 03. Plan priorizado de hitos

## Contexto y reglas de trabajo

**Fecha límite:** 23 de noviembre de 2026. **Entregables requeridos:** código funcionando e informe. La exposición no está indicada como entregable requerido.

El objetivo es completar primero un flujo mínimo de punta a punta antes de ampliar la evaluación. La secuencia prioriza una API propia, el análisis Git/OpenAPI, la generación de candidatos con Gemini, la revisión humana, Pytest, la ejecución real y GitHub Actions. Cada hito de implementación tendrá pruebas propias, actualización del `README.md` y comandos exactos para Windows PowerShell con `.venv` activo. Se incorporarán solo las dependencias necesarias, justificadas en el commit correspondiente.

Cada hito se cerrará con validación y un commit independiente antes de avanzar; no se mezclarán hitos en un commit. Ningún resultado de ejecución se asignará a partir de una salida del LLM. No se comenzará la implementación hasta recibir aprobación explícita de este plan.

## Prioridad de entregables

| Prioridad | Alcance |
|---|---|
| **Imprescindible para la entrega** | API FastAPI de ejemplo y RF del SUT; mapeo determinista `rf_map.yaml`; diff de código Git y de OpenAPI con impacto trazable; generación de candidatos con Gemini; tabla humana para editar/aprobar/rechazar y exportación XLSX básica con columnas obligatorias; solo casos aprobados generan Pytest; ejecución local de Pytest con resultado real; workflow manual protegido `workflow_dispatch` para generación y artefacto de candidatos; workflows automáticos `push`/`pull_request` en Linux; pruebas propias, instrucciones de README y un informe breve con el protocolo y los resultados realmente medidos. |
| **Opcional si sobra tiempo** | Formato avanzado del catálogo Excel (estilos complejos, filtros y formato condicional); análisis estático profundo de símbolos y correlación heurística más allá de la evidencia explícita; más de los tres cambios o más de tres generaciones por cambio; evaluación con segundo revisor; medición formal de significancia estadística; dashboard o comparación visual de métricas; integración directa de comentarios en Pull Requests. |

Las capacidades opcionales no pueden reemplazar las salvaguardas esenciales: revisión humana, separación entre decisión y estado, restricción del secret y trazabilidad entre RF del SUT, caso y archivo Pytest.

## Hitos y criterios de terminado

| Hito | Prioridad y periodo | Entregable | Criterio de terminado |
|---:|---|---|---|
| 0. Documentación y aprobación | Completado | Requisitos, arquitectura, plan y CI. | Documentos actualizados y aprobados; referencia correcta confirmada en la rama; aprobación explícita antes de iniciar código. |
| 1. API de ejemplo y contrato | Imprescindible — semana 1 | API FastAPI CRUD de elementos, OpenAPI versionable y `examples/sample_api/rf_map.yaml`. | La API tiene RF01.1–RF01.5 mapeados a sus métodos/rutas; sus pruebas verifican respuestas válidas, validación negativa y límites; se ejecutan sin servicios externos; README actualizado con comandos PowerShell. |
| 2. Detector Git/OpenAPI e impacto mínimo | Imprescindible — semana 1 | Comparación de revisiones de código y contrato, con informe de evidencia asociada. | Pruebas cubren cambios de archivos, cambios OpenAPI, ausencia/invalidación de contrato y hallazgos con una sola fuente; la salida enlaza operaciones con RF del SUT mediante el mapa y marca incertidumbres. README actualizado. |
| 3. Generación y revisión humana | Imprescindible — semana 2 | Generación con Gemini configurable, tabla local editable con decisión por caso y exportación XLSX básica. | Pruebas sin llamadas reales validan estructura, IDs, técnicas, datos HTTP, orden de columnas y contenido XLSX; errores de API/configuración son visibles; los casos comienzan Pendiente, No ejecutado y No automatizado; editar, aprobar y rechazar no falsifica el estado. README actualizado. |
| 4. Pytest, ejecución y flujo integrado | Imprescindible — semana 2 | Generador desde casos aprobados, ejecución local real e integración de extremo a extremo. | Pruebas demuestran que solo los aprobados producen Pytest y que cada prueba conserva CP y RF; la suite del SUT usa `TestClient` en proceso; los resultados Exitoso/Fallido provienen de Pytest y casos no corridos siguen No ejecutado. El flujo desde diff hasta reporte local funciona y está documentado en README. |
| 5. GitHub Actions y generación manual | Imprescindible — semana 2 | Workflow Linux para `push`/`pull_request` y workflow manual `workflow_dispatch` para generar candidatos en rama de confianza. | El workflow automático ejecuta la API de ejemplo con `TestClient`, los tests aprobados y publica resultados aunque fallen. El manual solo permite el contexto de la rama predeterminada de confianza, usa el secret sin imprimirlo ni subirlo, entrega candidatos como artefacto y no los aprueba ni ejecuta. Los YAML y límites de permisos se verifican; README actualizado. |
| 6. Evaluación e informe | Imprescindible — semana 3 (23 nov) | Tabla de resultados y `docs/informe-evaluacion.md`. | Se ejecuta el protocolo de tres cambios, dos defectos por cambio y tres generaciones por cambio; se incluyen la línea base manual, métricas con denominadores, resultados observados y limitaciones. No se inventan ni completan anticipadamente resultados. |
| 7. Pulido opcional | Solo si queda margen | Mejoras de presentación y análisis adicional. | No retrasa ni debilita los criterios imprescindibles ni la entrega del informe. Se valida y registra aparte. |

## Cronograma semanal

| Semana / fechas | Trabajo priorizado | Criterio de terminado de la semana |
|---|---|---|
| **Semana 1 — 9 al 15 de noviembre** | Implementar el fixture FastAPI, RF del SUT y `rf_map.yaml`; comparar el diff Git y las especificaciones OpenAPI; producir un resultado de impacto verificable. Preparar las pruebas unitarias/integración y el README inicial. | Una prueba automatizada confirma el mapeo de una operación del SUT desde un cambio Git/OpenAPI hasta RF01.x. La API y el detector funcionan en el entorno local siguiendo instrucciones PowerShell; el alcance de defectos y escenarios de la evaluación queda congelado. |
| **Semana 2 — 16 al 22 de noviembre** | Implementar Gemini y validación de candidatos; revisión tabular; generación de Pytest solo desde aprobados; ejecución con `TestClient`; integrar el flujo y configurar los dos workflows. Preparar y congelar los casos manuales antes de observar generaciones. | Flujo mínimo completo reproducible: cambio → impacto → generación → revisión → Pytest → ejecución/reporte. CI ejecuta las pruebas en Linux; el workflow manual genera artefactos de candidatos solo en rama de confianza y sin exponer la clave. |
| **Semana 3 — 23 de noviembre (cierre)** | Ejecutar las repeticiones de evaluación, calcular y verificar métricas, documentar los resultados reales, limitaciones y comandos de reproducción en `docs/informe-evaluacion.md`. Corregir solo defectos bloqueantes y volver a ejecutar validaciones afectadas. | Código y pruebas del MVP funcionan desde un entorno documentado; tabla de resultados completa con valores observados o N/A justificado; informe entregable sin resultados fabricados; todos los cambios están validados y commiteados. |

El cronograma es deliberadamente ajustado. Si aparece un retraso, se recortarán primero las capacidades opcionales; no se omitirá la aprobación humana, la protección de la clave, la ejecución real o la documentación de limitaciones.

## Protocolo de evaluación planeado

El protocolo detallado y las definiciones de métricas están en [01-documento-de-requisitos.md](./01-documento-de-requisitos.md). Para planificar el trabajo se fijan estos tamaños, sin implicar resultados:

- **Tres cambios controlados**, cada uno vinculado a una operación y RF de la API de ejemplo.
- **Dos defectos sembrados independientes por cambio** (seis en total), cada uno con oráculo verificable antes de incluirlo.
- **Línea base:** un conjunto manual por cambio, diseñado siguiendo el catálogo y congelado antes de la generación con Gemini.
- **Tres generaciones independientes de Gemini por cambio** (nueve en total), con modelo, prompt y contexto fijados; se documentará la variabilidad no determinista.
- Cada conjunto se ejecutará contra ambas variantes defectuosas de su cambio. Se registrará corrección, defectos detectados/ejecutados, cobertura de escenarios, casos negativos y límite, modificaciones humanas, tiempo de diseño/revisión y tokens/costo disponibles.
- La tabla entregable tendrá una fila por enfoque, cambio y repetición, además de resumen agregado por enfoque y limitaciones. Las celdas contendrán únicamente observaciones y resultados medidos.

Este tamaño permite una comparación exploratoria pareada dentro del plazo, pero no sustenta generalización estadística. Si un defecto no puede ser validado por una prueba de referencia, se excluirá y se justificará; no se contará como detectado o no detectado.

## Control de dependencias, pruebas y commits

- Se incluirán únicamente dependencias estrictamente necesarias; cada adición tendrá su justificación en el commit que la introduce.
- Cada hito de implementación incluirá pruebas propias automatizadas, salvo mediciones externas que se marquen explícitamente como manuales.
- `README.md` se actualizará en cada hito con instalación, configuración segura, comandos exactos de PowerShell (con `.venv` activo), ejecución y limitaciones.
- Los commits de implementación usarán `hito N: descripción` y se harán solo después de comprobar el criterio de terminado correspondiente.
- Las salidas del LLM, candidatos, aprobaciones y resultados Pytest se conservarán como entidades separadas y trazables.
- **No iniciar el hito 1 de implementación (API de ejemplo) ni ningún otro código hasta que la usuaria apruebe los ajustes documentales.**

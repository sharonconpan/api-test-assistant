# 04. Diseño del pipeline de CI

## 1. Objetivo

El pipeline valida los cambios de un repositorio de API y ejecuta en Linux las pruebas Pytest aprobadas que forman parte de la revisión. Debe proporcionar evidencia y reportes en cada commit o Pull Request, con credenciales y permisos mínimos.

La generación de casos con Gemini y su aprobación humana no se realizan automáticamente dentro de un workflow ordinario de Pull Request. El análisis de cambios puede ejecutarse en CI sin clave; las propuestas generadas y revisadas se incorporan al repositorio junto con sus pruebas Pytest para que la CI pueda ejecutarlas de forma reproducible.

## 2. Disparadores

- **`push`:** commits en las ramas configuradas para desarrollo e integración, como la rama principal y ramas de trabajo seleccionadas.
- **`pull_request`:** apertura, sincronización y reapertura de Pull Requests dirigidos a las ramas configuradas.

Los filtros de ramas y rutas se mantendrán explícitos y se ajustarán al flujo real del repositorio. Los eventos programados o manuales podrán añadirse posteriormente, pero no son necesarios para el alcance inicial.

## 3. Flujo de jobs

```mermaid
flowchart TD
    Event[push o pull_request] --> Checkout[Checkout con historial suficiente]
    Checkout --> Env[Preparar Python en Linux]
    Env --> Validate[Validar configuración, OpenAPI y código]
    Validate --> Impact[Analizar diff Git y OpenAPI]
    Validate --> Tests[Ejecutar Pytest aprobado]
    Impact --> Report[Consolidar reporte]
    Tests --> Report
    Report --> Upload[Publicar artefactos aunque haya fallos]
    Upload --> Result[Resultado del workflow]
```

### Job 1: Validación y preparación

- Ejecuta en un runner Linux.
- Descarga el repositorio y las revisiones necesarias para calcular el diff; obtiene historial suficiente, sin depender de un clon superficial que omita la revisión base.
- Configura una versión de Python fijada por el proyecto y restaura/instala las dependencias desde el manifiesto versionado.
- Ejecuta verificaciones de formato, configuración y validez de la especificación OpenAPI incorporadas por los hitos de implementación.
- Falla de manera visible ante contrato inválido o error de validación.

### Job 2: Análisis de impacto

- Determina el par de revisiones a comparar de acuerdo con el evento: base y head del Pull Request; para `push`, el commit anterior disponible y el commit nuevo, informando si la revisión anterior no existe.
- Ejecuta el detector Git y el comparador OpenAPI.
- Produce un resumen de archivos, operaciones y cambios de contrato, con la evidencia y las limitaciones de correlación.
- No llama a Gemini ni necesita `GEMINI_API_KEY`.
- Sube el resumen como artefacto. Un cambio OpenAPI que no pueda interpretarse debe generar un diagnóstico explícito y un estado fallido de validación, no un análisis aparentemente vacío.

### Job 3: Pruebas aprobadas

- Ejecuta con Pytest las pruebas disponibles en el commit del workflow, incluidas las pruebas aprobadas generadas y versionadas.
- No genera pruebas desde propuestas pendientes ni modifica decisiones humanas.
- Emite resultados estructurados (por ejemplo, JUnit XML) y cobertura cuando esté habilitada.
- Devuelve un estado fallido si alguna prueba falla. Solo los resultados reales de Pytest alimentan Estado `Exitoso` o `Fallido`; los casos que no se ejecutan siguen `No ejecutado`.

### Job 4: Reporte y artefactos

- Se ejecuta incluso si falla el análisis o la suite de pruebas, para conservar los diagnósticos y resultados disponibles.
- Publica los reportes de Pytest, cobertura (si está configurada), análisis de impacto, logs redactados y resumen de métricas.
- Usa nombres de artefacto que identifiquen la revisión y el intento de workflow; aplica una política de retención finita.
- No presenta una ejecución incompleta como exitosa. El estado global del workflow refleja el fallo de los jobs requeridos.

Los jobs podrán combinarse o separarse según las dependencias y tiempos medidos durante la implementación, pero el análisis, las pruebas y la publicación de resultados deben conservar estas responsabilidades y condiciones de fallo.

## 4. Uso de secretos y permisos

- La ejecución normal de análisis y pruebas **no requiere** `GEMINI_API_KEY`.
- La clave se almacena como GitHub Secret con alcance mínimo y nunca se escribe en el repositorio, logs, reportes, cachés ni artefactos.
- No se utilizará `pull_request_target` para hacer checkout y ejecutar código de un Pull Request.
- Los Pull Requests provenientes de forks se ejecutarán sin secrets; no se intentará obtener la clave desde una rama no confiable.
- Si una acción futura necesita generar casos con Gemini, debe tratarse como flujo separado y explícito, limitado a contexto de confianza y con revisión humana antes de generar Pytest.
- El workflow declarará los permisos mínimos necesarios (por defecto, solo lectura del contenido) y no concederá escritura de tokens, permisos administrativos o publicación de comentarios si no son necesarios.
- Las acciones de terceros se fijarán a versiones verificadas y, al implementar el workflow, se preferirán referencias inmutables por SHA.
- El contenido de un caso, nombre de rama, salida del LLM y log de prueba se considera entrada no confiable; no se interpolará directamente como código de shell ni se ejecutará como configuración del workflow.

## 5. Artefactos y reporte

El conjunto de artefactos debe permitir responder:

- ¿Qué revisión y evento se analizaron?
- ¿Qué archivos, operaciones OpenAPI y restricciones cambiaron?
- ¿Qué casos aprobados se ejecutaron y cuál fue el resultado real de cada uno?
- ¿Qué pruebas fallaron y cuáles no se ejecutaron?
- ¿Qué cobertura y métricas se obtuvieron, con qué denominadores?

Los artefactos podrán incluir:

1. Resultado JUnit de Pytest.
2. Reporte de cobertura, si se ejecutó y configuró.
3. Resumen JSON/Markdown del impacto Git/OpenAPI.
4. Reporte tabular de casos, RF, módulo, Estado y Automatizado, sin secretos.
5. Logs necesarios para diagnóstico, sujetos a redacción y retención limitada.

La hoja Excel editable es principalmente un artefacto de revisión local/versionado; CI no debe sobrescribir las decisiones humanas. Un reporte de CI es una salida de ejecución, no sustituye el catálogo revisado ni la trazabilidad fuente.

## 6. Fallos y condiciones de éxito

El workflow falla si una verificación requerida, la validación del contrato, el análisis requerido o una prueba Pytest falla. La falta de una revisión base puede limitar el diff de un primer `push`; el job lo reporta como tal y aplica la política configurada sin inventar cambios. Un fallo de infraestructura se distingue de un fallo de aserción, pero no se presenta como aprobación.

La publicación del artefacto debe intentarse aun cuando fallen los jobs anteriores. Si la publicación también falla, esa condición queda explícita en el resultado. No se asigna `Exitoso` a casos sin ejecución, a ejecuciones omitidas ni a flujos con error de configuración.

## 7. Configuración inicial y protección de ramas

Antes de habilitar protección de ramas, se identificará el nombre del job requerido y se configurarán reglas para exigir el workflow en Pull Requests. Las versiones de Python y dependencias se mantendrán reproducibles según las decisiones de implementación. La presencia de `GEMINI_API_KEY` no será un requisito para pasar la CI de pruebas aprobadas; la generación de nuevos casos se gestiona fuera del camino de ejecución ordinario.

## 8. Correspondencia con el flujo de la herramienta

El flujo general es:

**Commit / Pull Request → detección de cambios Git y OpenAPI → análisis de impacto → propuesta de casos → revisión/aprobación humana → generación y versionado de Pytest → ejecución en CI → reporte.**

CI automatiza la detección, validación, ejecución y publicación de resultados. La generación asistida y la decisión de aprobar se mantienen como etapas controladas para reducir exposición de secretos y evitar que una propuesta no revisada se convierta en código ejecutable.

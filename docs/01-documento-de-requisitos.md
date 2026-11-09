# 01. Documento de requisitos

## 1. Introducción

Este documento define los requisitos de una herramienta de apoyo al testing de APIs REST. La herramienta relaciona los cambios de un repositorio con su contrato OpenAPI, propone casos de prueba mediante un modelo de lenguaje (LLM), los presenta para revisión humana y transforma únicamente los casos aprobados en pruebas Pytest. Las pruebas se ejecutan localmente o mediante integración continua y sus resultados se reportan a partir de ejecuciones reales.

La propuesta responde al esfuerzo manual que implica determinar qué comportamiento puede verse afectado por un cambio y mantener pruebas útiles, especialmente escenarios negativos, casos límite y dependencias entre componentes. La generación asistida busca reducir tareas repetitivas sin asumir que una salida de IA es correcta ni retirar al desarrollador del proceso.

Como antecedente únicamente, existe un experimento previo denominado **DeltaHeal**, que comparó generación de pruebas con LLM frente a una línea base tradicional. Se cita como antecedente de investigación; esta propuesta no depende de su código, datos, configuración ni resultados.

## 2. Antecedentes y motivación

### 2.1 APIs REST

REST es un objeto de estudio pertinente porque las APIs REST exponen contratos observables mediante recursos, métodos HTTP, parámetros, cuerpos y códigos de respuesta; estos elementos permiten derivar escenarios verificables y relacionar cambios de implementación con cambios de contrato. OpenAPI ofrece una descripción estructurada de operaciones y restricciones que puede compararse entre revisiones. La prevalencia de REST en aplicaciones web y la distribución de defectos entre niveles de prueba deberán sustentarse en las fuentes del mapeo sistemático, no asumirse como resultados de este proyecto. **[CITAR S0X del mapeo sistemático]**

### 2.2 LLM para pruebas de APIs

El estado del arte debe revisar estudios empíricos que usan LLM para generar, priorizar o reparar pruebas de APIs, incluidos sus métodos de evaluación, líneas base, capacidad para cubrir entradas válidas e inválidas, detección de defectos, reproducibilidad y necesidad de revisión humana. También se deben documentar limitaciones como alucinaciones, dependencia del prompt, variabilidad entre ejecuciones y costo. Estas afirmaciones se completarán y contrastarán con las fuentes identificadas en el mapeo sistemático; no se atribuyen aquí resultados a estudios específicos. **[CITAR S0X del mapeo sistemático]**

La brecha que aborda esta propuesta es evaluar un flujo integrado y supervisado —cambios Git y OpenAPI, generación de casos, revisión humana, Pytest, CI/CD y reporte— en lugar de tratar la generación del LLM como equivalente a pruebas correctas o útiles.

## 3. Objetivo de investigación

Diseñar, implementar y evaluar un flujo integrado para automatizar, con supervisión humana, la generación y ejecución de pruebas de APIs REST a partir de cambios de código y de especificación. La evaluación determinará hasta qué punto el uso de IA puede reducir el esfuerzo manual manteniendo la corrección, capacidad de detección de defectos y cobertura de escenarios de las pruebas.

### 3.1 Preguntas de investigación e hipótesis

La evaluación es exploratoria y de alcance acotado; las hipótesis son preguntas contrastables, no resultados esperados garantizados.

| Código | Pregunta de investigación |
|---|---|
| PI1 | ¿Qué proporción de los casos generados con Gemini, después de la revisión humana, es correcta y ejecutable frente a casos diseñados manualmente siguiendo el catálogo? |
| PI2 | ¿Cómo se compara la capacidad de detección de defectos y la cobertura de escenarios de ambos enfoques en los cambios evaluados? |
| PI3 | ¿Qué esfuerzo de revisión y qué proporción de modificaciones requiere el conjunto generado con Gemini, y qué presencia tiene de casos negativos y límite? |

| Código | Hipótesis exploratoria |
|---|---|
| H1 | En los cambios evaluados, la tasa de detección de defectos de los casos aprobados con asistencia de Gemini será comparable a la de la línea base manual. |
| H2 | El tiempo mediano de diseño y preparación, incluida la revisión humana, será menor con asistencia de Gemini que con el diseño manual. |

Por el tamaño reducido de la muestra, los resultados se interpretarán descriptivamente y no se generalizarán como prueba estadística para todas las APIs o modelos.

### 3.2 Protocolo de evaluación

Se usará un protocolo pequeño, pareado y reproducible sobre la API de ejemplo. Antes de generar casos se congelarán los escenarios de referencia, el contrato de la versión limpia y los cambios evaluados.

1. **Cambios:** evaluar tres cambios controlados y versionados, cada uno vinculado a una operación y RF de la API de ejemplo. Se conservarán el diff Git, el diff OpenAPI y el commit exacto.
2. **Defectos:** para cada cambio se prepararán dos variantes defectuosas independientes y documentadas (seis defectos en total). Cada variante debe ser activable/reproducible, tener un oráculo claro y ser detectada por al menos una prueba de referencia antes de incluirse. No se introducirán defectos cuya detección no pueda validarse.
3. **Línea base:** para cada cambio, una persona diseñará un conjunto de casos manuales siguiendo el mismo catálogo, contrato y escenarios disponibles para Gemini. Se congelará antes de observar las generaciones del LLM.
4. **Gemini:** se harán tres generaciones independientes por cambio (nueve generaciones en total) con el mismo modelo configurado, instrucción, esquema, evidencia y límites de contexto. Se registrarán la configuración no secreta, fecha, duración y tokens/costo disponibles. Si el proveedor no permite fijar una semilla, se documentará que las repeticiones son no deterministas.
5. **Revisión:** un mismo revisor aplicará una rúbrica fija a casos manuales y generados. Para cada caso marcará corrección, aprobación/rechazo, modificación sustancial o de formato, tipo de escenario y tiempo de revisión. La línea base no se alterará después de ver la salida del LLM.
6. **Ejecución:** cada conjunto de casos manual y cada repetición de Gemini se ejecutará contra las dos variantes defectuosas de su cambio correspondiente. Un defecto se contará como detectado solo si una prueba asociada falla por una aserción pertinente al defecto; errores de infraestructura se excluirán y reportarán aparte.
7. **Cobertura:** antes de generar los casos se fijará una lista de escenarios esperados por operación, incluidos los negativos y los valores límite derivables del contrato. Se medirá la presencia de cada escenario entre los casos aprobados.

La matriz de resultados tendrá una fila por conjunto/corrida y las columnas: **Cambio**, **RF**, **Enfoque (manual/Gemini)**, **Repetición**, **Casos propuestos**, **Casos correctos**, **Casos aprobados**, **Defectos detectados/ejecutados**, **Escenarios cubiertos/definidos**, **Casos negativos**, **Casos límite**, **Casos modificados sustancialmente**, **Tiempo de diseño/generación**, **Tiempo de revisión**, **Tokens/costo disponible** y **Observaciones**. Se reportarán los denominadores y datos ausentes; no se rellenarán resultados por anticipado. Un resumen agregado presentará las mismas métricas por enfoque, además de limitaciones y resultados fallidos de infraestructura.

Este protocolo contrasta la capacidad del generador en tres cambios, no mide de manera exhaustiva todos los tipos de APIs, y sus números son el tamaño planeado de la muestra, no resultados observados.

### 3.3 Métricas de evaluación

Las métricas se calcularán sobre un conjunto de cambios y escenarios de referencia documentados y reproducibles. Para las proporciones, se informará el numerador, denominador y tamaño de muestra; las métricas sin casos aplicables se marcarán como **N/A**, no como cero.

| Métrica | Definición operacional |
|---|---|
| Corrección de los casos | Porcentaje de casos revisados por una persona evaluadora que son válidos, coherentes con el contrato y ejecutables con el comportamiento esperado especificado: casos clasificados como correctos / casos revisados × 100. Se reportará también la concordancia entre evaluadores si participan varios. |
| Detección de defectos | Porcentaje de defectos conocidos del conjunto de evaluación que provocan el fallo de al menos una prueba generada: defectos detectados / defectos sembrados o de referencia ejecutados × 100. Se registrará cada defecto y la evidencia del fallo. |
| Cobertura de escenarios | Porcentaje de escenarios definidos previamente para cada operación y cambio que están representados por al menos un caso aprobado. La lista y el método de conteo se fijarán antes de evaluar cada conjunto. |
| Casos negativos | Proporción y cantidad de casos aprobados dirigidos a entradas inválidas, restricciones incumplidas o respuestas de error; se informarán por operación y por conjunto evaluado. |
| Casos límite | Proporción y cantidad de casos aprobados que ejercitan límites documentados o deducibles del contrato, como mínimos, máximos, límites de longitud o cardinalidad. Se distinguirán de los casos negativos cuando el límite sea inválido. |
| Modificación humana | Porcentaje de casos generados que requieren cambios sustanciales antes de aprobarse: casos modificados sustancialmente / casos generados revisados × 100. Se distinguirán cambios de contenido, correcciones de datos y ajustes de formato; también se informarán rechazos y aprobaciones sin cambios. |
| Esfuerzo de revisión | Tiempo empleado por el revisor para corregir, aprobar o rechazar casos, medido por conjunto y, cuando sea posible, comparado con el diseño manual de casos equivalentes. |

El estado **Exitoso/Fallido** de un caso representa exclusivamente el resultado de ejecutar su prueba Pytest. No lo determina el LLM ni una revisión estática. Los casos aún no ejecutados conservan el estado **No ejecutado**.

## 4. Alcance

La primera versión se enfocará en repositorios Python que exponen APIs REST y disponen de una especificación OpenAPI local, versionada o recuperable desde el repositorio. Permitirá comparar revisiones Git, analizar cambios de código y de especificación, generar casos propuestos, revisarlos en una interfaz tabular, exportarlos a Excel, generar Pytest desde los aprobados y ejecutar/reportar los resultados.

Se incluirá una API pequeña de ejemplo basada en FastAPI dentro de `examples/`, con una especificación OpenAPI utilizable para demostrar y probar el flujo de extremo a extremo. Esta API será un fixture local de la herramienta, no un servicio externo ni una dependencia de DeltaHeal. Los identificadores RF incluidos en los casos pertenecen a los requisitos funcionales de esta **API bajo prueba (SUT)**, no a los requisitos funcionales RF01–RF11 de la herramienta.

### 4.1 Requisitos funcionales de la API de ejemplo (SUT)

La API de ejemplo será un CRUD mínimo de elementos (`items`). Su archivo versionado `examples/sample_api/rf_map.yaml` asignará explícitamente cada operación HTTP a su RF y módulo. El analizador usará el método y la ruta normalizada como clave; el mapeo también podrá documentar `operationId` para hacer la asignación más robusta. No se delegará al LLM la asignación de RF, ya que el mapeo declarativo es revisable, determinista y puede validarse contra OpenAPI.

| RF del SUT | Módulo | Operación OpenAPI |
|---|---|---|
| RF01.1 — Crear elemento | Gestión de elementos | `POST /items` |
| RF01.2 — Listar elementos | Gestión de elementos | `GET /items` |
| RF01.3 — Consultar elemento | Gestión de elementos | `GET /items/{item_id}` |
| RF01.4 — Actualizar elemento | Gestión de elementos | `PUT /items/{item_id}` |
| RF01.5 — Eliminar elemento | Gestión de elementos | `DELETE /items/{item_id}` |

Cada caso se asignará al RF del SUT indicado por la operación principal que verifica. Una ruta/método ausente del mapa deberá producir un diagnóstico para completar la asignación; no se inventará un RF ni se reutilizará un RF de la herramienta. Cada ID de caso seguirá usando el RF del SUT, por ejemplo `CP-RF01.1-01`.

## 5. Actores

| Actor | Responsabilidad |
|---|---|
| Desarrollador | Configura el repositorio, revisa y edita los casos sugeridos, los aprueba o rechaza y consulta las pruebas y reportes. |
| Revisor | Valida que los casos aprobados sean pertinentes, verificables y coherentes con el contrato y las reglas de negocio conocidas. Puede ser el mismo desarrollador. |
| CI (GitHub Actions) | Valida y ejecuta las pruebas disponibles en un entorno Linux ante los eventos configurados, conserva reportes y artefactos y comunica resultados. No aprueba casos ni inventa estados. |
| Gemini | Servicio LLM que propone casos a partir del contexto acotado de cambios y OpenAPI; sus salidas se consideran no confiables hasta la revisión humana. |

## 6. Requisitos funcionales de la herramienta

### RF01. Selección de revisiones y detección de cambios Git

La herramienta permitirá elegir o recibir una revisión base y una revisión destino para analizar commits, ramas o cambios asociados a un Pull Request.

**Criterios de aceptación**
- Se puede obtener un diff reproducible entre las revisiones seleccionadas.
- Se identifican rutas de archivos modificados, añadidos, eliminados y renombrados.
- Una referencia Git inexistente o un repositorio no válido produce un error explícito y no un análisis vacío con apariencia de éxito.

### RF02. Detección de cambios OpenAPI

La herramienta comparará las especificaciones OpenAPI de las revisiones base y destino, cuando ambas estén disponibles, e identificará operaciones, parámetros, cuerpos, restricciones y respuestas añadidos, eliminados o modificados.

**Criterios de aceptación**
- Se conserva la revisión y ubicación de cada especificación analizada.
- Se informa si falta una especificación en una de las revisiones o si no se puede interpretar.
- La ausencia de cambios en el contrato se distingue de la imposibilidad de analizarlo.

### RF03. Análisis de impacto combinado

La herramienta relacionará el diff de código con el diff OpenAPI para identificar endpoints, funcionalidades y reglas de validación potencialmente afectados. El diff de código aporta archivos y símbolos modificados; el diff de OpenAPI aporta operaciones y elementos del contrato modificados. Se correlacionarán mediante rutas, métodos HTTP, identificadores de operación, referencias a esquemas y asociaciones de código configurables o detectables. Los impactos concordantes se priorizarán; los cambios presentes solo en una fuente se conservarán como evidencia separada con su nivel de incertidumbre, sin inferir una correspondencia inexistente.

**Criterios de aceptación**
- Cada impacto candidato incluye la evidencia de código y/o de contrato que lo sustenta.
- Los impactos con ambas fuentes relacionadas pueden distinguirse de los impactos sustentados por una sola fuente.
- El análisis no afirma que un endpoint está afectado si no existe evidencia verificable; las asociaciones heurísticas se marcan como tales.

### RF04. Generación de casos con Gemini

La herramienta solicitará casos al modelo Gemini configurado mediante `GEMINI_MODEL` (por defecto `gemini-3.8-flash`) y la clave `GEMINI_API_KEY`, usando únicamente el contexto pertinente del análisis y del contrato.

**Criterios de aceptación**
- Las credenciales se obtienen del entorno y nunca se guardan en código, casos exportados, logs, reportes ni artefactos.
- La salida se valida antes de incorporarse al conjunto de casos y los errores de configuración, cuota o respuesta inválida se presentan explícitamente.
- Una propuesta del LLM no se considera aprobada, ejecutada ni exitosa por el hecho de haberse generado.

### RF05. Presentación, edición y decisión humana

La herramienta presentará los casos en una tabla editable. El revisor podrá aprobar o rechazar individualmente cada caso; la decisión de revisión será independiente del estado de ejecución.

**Criterios de aceptación**
- Se respeta el orden obligatorio de las nueve columnas del catálogo y los valores cerrados de Técnica, Estado y Automatizado.
- Se admiten decisiones de revisión **Pendiente**, **Aprobado** o **Rechazado**, sin confundirlas con **No ejecutado**, **Exitoso** o **Fallido**.
- La tabla permite editar los datos del caso y conservar su identificación y trazabilidad.
- Solo un caso con decisión **Aprobado** puede pasar al generador de Pytest.

### RF06. Intercambio y exportación

La herramienta permitirá serializar los casos para intercambio estructurado y exportarlos a un archivo Excel editable con hojas de casos y resumen.

**Criterios de aceptación**
- El formato estructurado conserva identificadores, datos HTTP, decisiones, estado, aprobación y trazabilidad.
- El Excel respeta el orden de columnas del catálogo, añade al final los datos específicos de API y ofrece agrupación por requisito funcional.
- Existe un bloque de métricas por RF con total de casos, distribución por técnica, estados (Exitoso, Fallido y, antes de ejecutar, No ejecutado) y porcentaje de aprobación.
- Existe una hoja de resumen por módulo con **#Casos**, **Exitoso**, **Fallido** y **Automatizado**.

### RF07. Generación de pruebas Pytest

La herramienta generará pruebas ejecutables exclusivamente para casos aprobados.

**Criterios de aceptación**
- Los casos pendientes o rechazados no generan pruebas ejecutables.
- Cada prueba conserva un identificador de caso y su requisito funcional de origen.
- La salida generada se puede inspeccionar antes de ejecutarla y no incluye credenciales.

### RF08. Ejecución y actualización del estado

La herramienta ejecutará las pruebas con Pytest y actualizará el estado de cada caso a partir del resultado real de su prueba asociada.

**Criterios de aceptación**
- El resultado del runner se conserva como evidencia y determina **Exitoso** o **Fallido**.
- Los casos sin prueba generada o no ejecutados permanecen **No ejecutado**.
- Un fallo de infraestructura o de configuración se informa separadamente y no se presenta como un caso exitoso.

### RF09. Integración continua y reportes

La solución incluirá workflows de GitHub Actions para validar y ejecutar pruebas en Linux en eventos `push` y `pull_request`, y un workflow manual `workflow_dispatch` para generar casos candidatos con Gemini desde la rama predeterminada de confianza y publicarlos como artefacto para revisión.

**Criterios de aceptación**
- El workflow no expone secretos a código no confiable de Pull Requests ni requiere una clave Gemini para ejecutar pruebas ya generadas.
- La generación manual valida la rama de confianza, no ejecuta el código del SHA destino, excluye y redacta secretos del contexto, no imprime la clave y publica solo candidatos no aprobados como artefacto; estos no generan ni ejecutan Pytest hasta su aprobación humana.
- Un job fallido hace fallar el workflow correspondiente y queda visible en el reporte.
- Los artefactos permiten vincular resultados, pruebas y casos sin incluir secretos.

### RF10. Evaluación y trazabilidad

La herramienta mantendrá relaciones verificables entre requisitos funcionales, casos, decisiones de revisión, pruebas Pytest y resultados. La evaluación reportará las métricas descritas en la sección 2.

**Criterios de aceptación**
- Se puede seguir un requisito funcional hasta sus casos y archivos Pytest, y volver desde un fallo al caso correspondiente.
- Las métricas se calculan sobre datos registrados y expresan sus denominadores.
- La línea base, cambios evaluados, versión del modelo/configuración no secreta y resultados quedan documentados para reproducibilidad.

### RF11. API de ejemplo

El repositorio incluirá una API mínima autocontenida para validar el flujo, su integración con OpenAPI y las pruebas generadas.

**Criterios de aceptación**
- La aplicación y la especificación pueden ejecutarse/consultarse localmente siguiendo instrucciones documentadas.
- El ejemplo cubre al menos una operación con entradas válidas, inválidas y límites comprobables.
- La aplicación no requiere acceder a repositorios externos para ejecutarse.

## 7. Formato obligatorio de los casos de prueba

Las primeras nueve columnas y su orden son:

| Orden | Columna | Regla |
|---:|---|---|
| 1 | ID | Patrón `CP-<RF>-<número de dos dígitos>`, por ejemplo `CP-RF02.1-01`. |
| 2 | Técnica | Solo `T. Decisión (valida)`, `T. Decisión (invalida)`, `EP (valida)` o `EP (invalida)`. |
| 3 | Descripción del Caso | Descripción concreta y verificable del escenario. |
| 4 | Precondiciones | Estado o datos necesarios antes de ejecutar el caso. |
| 5 | Datos de Entrada | Valores del escenario; no incluir secretos. |
| 6 | Pasos | Acciones reproducibles para ejecutar el caso. |
| 7 | Resultado Esperado | Comportamiento verificable y respuesta esperada. |
| 8 | Estado | `No ejecutado` antes de correr; `Exitoso` o `Fallido` solo según ejecución real. |
| 9 | Automatizado | `No` hasta que exista Pytest asociado; `Si` cuando ya fue generado. |

Al final se añadirán, en este orden, las columnas de API: **Método HTTP**, **Endpoint**, **Parámetros**, **Cuerpo**, **Código de respuesta esperado**. La decisión de revisión (**Pendiente**, **Aprobado** o **Rechazado**) y la trazabilidad a la prueba son metadatos separados; no alteran las nueve columnas obligatorias. La revisión de un caso por sí sola no cambia su Estado ni el valor de Automatizado.

No se amplía el conjunto permitido de técnicas en esta etapa. Si una futura evaluación requiere una categoría específica de valores límite, se documentará como extensión compatible y se acordará antes de incorporarla al formato.

## 8. Matriz de trazabilidad RF → CP → archivo Pytest

La siguiente matriz usa los RF de la API de ejemplo (SUT), no los RF de la herramienta. Los IDs y rutas Pytest son plantillas de trazabilidad para los casos que se definan durante la implementación; no representan casos generados ni resultados de ejecución.

| Requisito funcional | Caso(s) CP | Archivo Pytest asociado |
|---|---|---|
| RF01.1 — Crear elemento | CP-RF01.1-01… | `examples/sample_api/tests/generated/test_rf01_1_*.py` |
| RF01.2 — Listar elementos | CP-RF01.2-01… | `examples/sample_api/tests/generated/test_rf01_2_*.py` |
| RF01.3 — Consultar elemento | CP-RF01.3-01… | `examples/sample_api/tests/generated/test_rf01_3_*.py` |
| RF01.4 — Actualizar elemento | CP-RF01.4-01… | `examples/sample_api/tests/generated/test_rf01_4_*.py` |
| RF01.5 — Eliminar elemento | CP-RF01.5-01… | `examples/sample_api/tests/generated/test_rf01_5_*.py` |

En la implementación, la matriz se actualizará con las relaciones reales entre cada RF, sus IDs `CP-...` y las rutas Pytest generadas. Un requisito de infraestructura o proceso puede no tener un caso de API aplicable; en ese caso se documentará como **N/A justificado**, no se crearán casos ficticios.

## 9. Requisitos no funcionales

- **Reproducibilidad:** registrar revisiones Git, hash o versión del contrato, configuración no secreta, modelo y versión del generador cuando estén disponibles, decisiones humanas y resultados. Evitar depender de respuestas no versionadas para repetir ejecuciones.
- **Seguridad de la clave:** mantener `GEMINI_API_KEY` fuera del repositorio y de los artefactos; usar variables de entorno localmente y GitHub Secrets en CI. No exponer secretos a workflows de Pull Requests desde forks.
- **Costo y tokens:** limitar el contexto a cambios e información OpenAPI pertinentes, evitar solicitudes duplicadas cuando sea seguro, reportar consumo/costo disponible y permitir operar sobre casos previamente generados sin llamar al LLM.
- **Trazabilidad:** conservar IDs estables y enlaces entre cambio, operación, RF, caso, decisión, archivo Pytest, ejecución y reporte.
- **Rendimiento:** completar análisis de repositorios pequeños y la interacción de revisión en tiempos adecuados para uso interactivo; medir duración y tamaño del corpus antes de fijar umbrales cuantitativos.
- **Confiabilidad:** validar las respuestas estructuradas del LLM, manejar límites y errores explícitamente y no convertir ausencia de datos en una salida exitosa.
- **Usabilidad y compatibilidad:** proporcionar instrucciones en español y comandos reproducibles para Windows PowerShell, además de ejecución de CI en Linux.
- **Mantenibilidad:** separar responsabilidades de Git, OpenAPI, generación, revisión, exportación, Pytest y reportes.

## 10. Restricciones

- El modelo objetivo es Gemini, configurable mediante `GEMINI_MODEL`, cuyo valor predeterminado será `gemini-3.8-flash`.
- La clave se obtiene únicamente de `GEMINI_API_KEY`; no se acepta una clave escrita en el código o en archivos versionados.
- Solo los casos aprobados por una persona se convierten en pruebas ejecutables.
- El estado de ejecución deriva exclusivamente de resultados reales de Pytest.
- El formato del catálogo y sus valores permitidos son obligatorios; los campos específicos de API se agregan después de las nueve columnas base.
- La ejecución CI se realizará en Linux y se integrará con GitHub Actions.
- El repositorio debe poder probarse sin depender del código de DeltaHeal ni de otro repositorio externo.

## 11. Supuestos

- El repositorio objetivo contiene suficiente historia Git para comparar dos revisiones.
- Existe una especificación OpenAPI legible en al menos una de las revisiones; cuando no exista, la herramienta informará la limitación y podrá presentar impactos sustentados solo en código.
- El contrato OpenAPI describe las operaciones y restricciones relevantes con fidelidad razonable.
- El usuario puede proporcionar, durante la revisión, reglas de negocio no expresadas en el contrato.
- Los casos de evaluación y defectos de referencia pueden definirse y revisarse independientemente de las salidas del LLM.
- La API FastAPI de `examples/` es un ejemplo de validación, no una dependencia impuesta a todos los repositorios analizados.

## 12. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| El LLM propone casos incorrectos, redundantes o no verificables. | Validar estructura, mostrar evidencia y mantener aprobación humana obligatoria. |
| Cambios de código y contrato no pueden correlacionarse con certeza. | Informar evidencia y confianza por fuente; permitir asociación configurable y evitar afirmar impacto sin sustento. |
| El contrato está desactualizado o incompleto. | Señalar discrepancias, registrar la versión analizada y presentar limitaciones al revisor. |
| Las pruebas generadas son frágiles o verifican solo detalles accidentales. | Revisar las aserciones, generar pruebas desde casos estructurados y evaluar corrección y detección de defectos. |
| Costos, cuota o latencia del LLM impiden una corrida. | Acotar tokens, reportar fallos y permitir revisar/exportar casos ya persistidos sin nuevas llamadas. |
| La clave se filtra mediante logs, artefactos o CI. | No serializarla, redactar variables sensibles y restringir secrets según el evento y nivel de confianza. |
| El resultado no es reproducible porque el modelo cambia. | Guardar metadatos no sensibles, entradas relevantes, casos recibidos y decisiones; separar reproducibilidad de la ejecución de pruebas de la reproducibilidad de la generación. |
| El conjunto de evaluación favorece al generador o mide métricas inconsistentes. | Definir escenarios y defectos de referencia antes de ejecutar; documentar denominadores, exclusiones y protocolo. |
| Pull Requests no confiables ejecutan código con permisos excesivos. | Usar permisos mínimos, no exponer secrets a forks y separar la ejecución de código de la disponibilidad de credenciales. |

## 13. Fuera de alcance

- Reemplazar el juicio del desarrollador o aprobar casos automáticamente.
- Garantizar que una prueba generada demuestre ausencia de defectos.
- Probar todas las reglas de negocio cuando no estén descritas en OpenAPI, código o contexto proporcionado.
- Ejecutar pruebas destructivas contra servicios de producción o APIs externas.
- Implementar de inicio agentes autónomos con permisos para cambiar el código del repositorio o aprobar Pull Requests.
- Replicar, modificar o depender de DeltaHeal, de su código o de sus resultados experimentales.
- Añadir técnicas de prueba distintas de las cuatro permitidas sin documentarlas y aprobarlas como extensión.
- Evaluar rendimiento de producción o sustituir suites unitarias, de integración y aceptación existentes.

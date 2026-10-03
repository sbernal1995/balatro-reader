# Lector y simulador de Balatro

Asistente local con lectura en vivo, historial de partida y simulación de la ciega completa. **[Instalación en otra PC](INSTALACION.md)** · [Descargas del motor](https://github.com/sbernal1995/balatro-reader/releases).

Después de instalar, abrí `Iniciar.cmd` y pulsá **Simular** en [el panel local](http://127.0.0.1:8765). El asistente recomienda acciones; las realizás vos en Balatro.

## Reglas incorporadas

El motor cubre el contenido del juego base:

- **150 comodines**, incluidos efectos sobre puntuación, cartas jugadas y retenidas, repeticiones, crecimiento, destrucción, dinero, creación de cartas, copias de Blueprint/Brainstorm y efectos de venta.
- **28 ciegas jefe**, incluidas restricciones de mano, debilidades por palo o figuras, historial de El Ojo y La Boca, cartas ocultas, descarte forzado, selección obligatoria, cambios de recursos y desactivación del jefe.
- Las **12 categorías de manos**, sus niveles, fichas, multiplicadores y cantidades jugadas en la ronda y en la partida.
- Los 13 valores y 4 palos de las cartas; las **8 mejoras**, incluida Lucky; ediciones Foil, Holográfica, Policromada y Negativa donde corresponda; los **4 sellos** y bonos permanentes.
- **22 Tarot, 12 planetas y 18 espectrales**, con selección de objetivos, copia, mejora, destrucción, creación de cartas y cambios de niveles, dinero y recursos. La Muerte compara ambas direcciones de copia.
- Interacciones con los vales ya adquiridos, probabilidades actuales y límites reales de mano, comodines y consumibles. Incluye puntuación de la baraja Plasma.

[Catálogo de contenido y ubicación de las reglas](REGLAS.md). La búsqueda también compara **usar consumibles y vender comodines o consumibles** durante la ciega. Por ejemplo, vender un comodín puede desactivar La Hoja, vender al Luchador puede desactivar un jefe y una venta puede aumentar Fogata. Respeta comodines eternos, incluidos Ankh y Hex, el valor de venta y cobro de alquiler, y la caducidad de los perecederos. Las copias conservan esas pegatinas.

## Cómo decide

Compara todas las selecciones de 1 a 5 cartas para jugar o descartar como primera acción, las selecciones legales para los consumibles disponibles y las ventas permitidas. Para cada opción simula **1000 rondas completas** desde el estado actual. Acumula fichas, repone cartas sin reemplazo, actualiza habilidades y recursos y permite encadenar descartes y consumibles. Detiene cada ronda al ganar, perder o alcanzar el límite de búsqueda de 64 acciones.

La prioridad es la **mayor probabilidad estimada de superar esta ciega**. Entre porcentajes iguales, prefiere menos manos de media entre las victorias, después más uso de los descartes disponibles, menos cartas usadas o vendidas del inventario y finalmente más fichas. Esto evita añadir ventas o consumibles innecesarios entre planes equivalentes. Una penalización al descartar se aplica dentro de cada ronda simulada, por ejemplo la pérdida de Mult del Comodín verde o la reducción de fichas de Estandarte.

Se muestra la probabilidad acumulada de ganar con una mano, con hasta dos, etc., las manos necesarias entre las victorias, fichas adicionales de media y un intervalo de Wilson del 95%. El intervalo refleja el muestreo individual; no incluye el error de la estrategia aproximada ni la selección de la mejor entre muchas opciones.

La selección inicial se enumera; el orden sugerido de cartas y las continuaciones se buscan con heurísticas. Después de cada robo, la estrategia evalúa candidatos de jugada y descarte y acciones de inventario sobre una observación independiente del futuro real. No enumera todas las secuencias ni todas las permutaciones de cartas o comodines. **El porcentaje no certifica el óptimo global**. El horizonte termina en esta ciega; no decide compras ni optimiza ciegas futuras, aunque el motor contiene las habilidades económicas correspondientes.

El simulador usa su propia semilla, independiente de la del juego, y muestras comunes entre las primeras acciones. La pila entra como composición canónica y se baraja para cada muestra. Las identidades ocultas se agrupan en una bolsa anónima y se reasignan en cada tirada; no se consulta la identidad de una posición oculta ni el orden futuro de robo. El orden de comodines ocultos también se muestrea. Las generaciones aleatorias respetan las cartas bloqueadas en el perfil cuando el mod actualizado exporta esa información.

## Interfaz y recálculo

El cálculo empieza solo al pulsar **Simular**. Durante el análisis aparecen resultados parciales a medida que cada opción termina sus 1000 rondas. Usa hasta ocho trabajadores; una mano de ocho cartas con varias manos, descartes y consumibles puede tardar varios minutos. La barra mide opciones terminadas.

Las recomendaciones muestran cartas por valor y palo, por ejemplo **As ♠** o **J ♥**, y resaltan las cartas de la mano o del inventario. Seguí el orden mostrado cuando corresponda. Después de jugar, descartar, usar o vender, pulsá **Simular** de nuevo. Cualquier cambio relevante de estado cancela el cálculo anterior y retira su recomendación. El lector continúa respondiendo durante el cálculo.

## Lectura y registro

La API se consulta cada segundo. Se guardan mano, pila de robo, descarte, colección, comodines, consumibles, niveles y usos de las manos, jefe activo y sus restricciones, historial de Tarot/planetas/espectrales, probabilidades y valores persistentes de cada carta.

- `registros/actual.json`: última captura con fecha UTC.
- `registros/historial.jsonl`: cambios observados.
- `registros/recomendacion.json`: último análisis terminado junto con su estado de entrada.

Estos archivos permanecen en tu PC y se excluyen de Git. Una carta o jefe ajeno al registro del juego base bloquea la recomendación con su clave. No se admite contenido adicional de mods ni se garantiza fidelidad de desafíos con reglas especiales. El modelo recibe la situación de la ciega ya iniciada; no reproduce el inicio de una partida de cada baraja o apuesta.

## Desarrollo y pruebas

La API procede de [BalatroBot](https://github.com/coder/balatrobot), revisión fijada por el instalador. `integrations/gamestate.lua` amplía su lectura y se copia al mod instalado. Reiniciá Balatro después de actualizarla.

El motor Rust procede de [balatroagent](https://github.com/jahankazimi078/balatroagent), vendorizado bajo MIT. Su revisión, licencia y cambios locales se detallan en [engine/UPSTREAM.md](engine/UPSTREAM.md). La interfaz Python lanza un proceso aislado que recibe JSON, calcula y transmite resultados parciales; el motor no tiene acceso a la API del juego.

Con Rust estable y las herramientas de compilación de la plataforma:

```powershell
cargo test --manifest-path engine/Cargo.toml --workspace --release --locked
cargo build --manifest-path engine/Cargo.toml --release --locked
.\.venv\Scripts\python.exe -m unittest test_native_engine test_reader test_simulator -v
```

Las pruebas del núcleo cubren evaluación de manos, puntuación, comodines, jefes, consumibles, sellos, economía y aleatoriedad. Las pruebas de integración recorren los 150 comodines, 28 jefes y 52 consumibles y verifican importación de valores actuales, copias, eternos, restricciones, cartas ocultas, consumibles, descartes encadenados, resultados parciales y cancelación. GitHub ejecuta las pruebas en Windows y Linux. El evaluador anterior de Python queda como referencia de regresión; el panel utiliza el motor Rust.

## Licencia

Código del lector bajo MIT. El núcleo conserva [su licencia MIT](engine/vendor/balatro-core/LICENSE); la ampliación de BalatroBot conserva [su licencia](integrations/LICENSE-BalatroBot.txt). Lovely y Steamodded se descargan de sus proyectos oficiales. El repositorio y el motor no incluyen el juego, su código fuente ni sus imágenes, sonidos o archivos de guardado.

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

Por defecto compara todas las selecciones de 1 a 5 cartas para jugar o descartar como primera acción, las selecciones legales para los consumibles disponibles y las ventas permitidas. El selector **Búsqueda** permite elegir **Genética · menos opciones** para evaluar una selección de candidatos. Usa **20 rondas completas por opción** para orientar la jugada. El selector de tiradas permite ampliar a **100 o 1000**. Acumula fichas, repone cartas sin reemplazo, actualiza habilidades y recursos y permite encadenar descartes y consumibles. Detiene cada ronda al ganar, perder o alcanzar el límite de búsqueda de 64 acciones.

La prioridad es la **mayor probabilidad estimada de superar esta ciega**. Entre porcentajes iguales, prefiere menos manos de media entre las victorias, después más uso de los descartes disponibles, menos cartas usadas o vendidas del inventario y finalmente más fichas. Esto evita añadir ventas o consumibles innecesarios entre planes equivalentes. Una penalización al descartar se aplica dentro de cada ronda simulada, por ejemplo la pérdida de Mult del Comodín verde o la reducción de fichas de Estandarte.

Se muestra la probabilidad acumulada de ganar con una mano, con hasta dos, etc., las manos necesarias entre las victorias, fichas adicionales de media y un intervalo de Wilson del 95%. El intervalo refleja el muestreo individual; no incluye el error de la estrategia aproximada ni la selección de la mejor entre muchas opciones.

La interfaz presenta **victorias observadas en la simulación**. Si todas las tiradas ganan, muestra el conteo real, por ejemplo **20 / 20**, y aclara que no es una garantía; si ninguna gana, muestra **0 / 20**. Los resultados intermedios usan porcentajes observados, sin redondear una frecuencia inferior a uno a 100%. El gráfico cuenta **manos adicionales desde el estado analizado**, incluyendo la jugada recomendada si corresponde. Las victorias pueden requerir descartes, consumibles o ventas, y jugadas posteriores adaptadas a los robos de cada tirada. No es la probabilidad de ganar con la primera jugada ni una secuencia fija de dos manos.

Un nuevo robo o efecto aleatorio aporta información y puede cambiar la estimación. Que todas las tiradas ganen no prueba que todo resultado real gane. El [intervalo de Wilson](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm) mide incertidumbre de muestreo bajo el modelo, no errores de las reglas implementadas. Las fichas de la primera jugada también se muestran como media simulada cuando interviene el azar. El modo rápido tiene mayor variación en porcentajes y ranking: si las opciones están parejas, conviene ampliar el análisis.

Debajo de la acción recomendada aparece **Camino para ganar · ejemplo simulado**, también durante los resultados parciales si la opción ya tiene una victoria. El enlace **Ver camino paso a paso** permite saltar al recorrido. Se muestran los pasos en orden: descartes, consumibles, ventas y manos jugadas, con cartas dibujadas y sus nombres, categoría, fichas por mano, total acumulado y recursos restantes. Durante el cálculo se marca como provisional y puede cambiar junto con la recomendación. Las probabilidades detalladas quedan después del camino en **Ver probabilidades y recursos del plan**.

Se elige una victoria con la menor cantidad de manos observada entre las tiradas de esa opción. Es un ejemplo de esos robos y efectos aleatorios; las jugadas posteriores dependen de recibir esas cartas. El porcentaje mostrado sigue correspondiendo al conjunto de tiradas. Si ninguna tirada ganó, se indica que no hay secuencia ganadora. La secuencia se guarda también en `registros/recomendacion.json` y en las recomendaciones parciales, y se oculta cuando cambia la partida para volver a calcular.

Las selecciones iniciales legales se enumeran; el modo clásico las evalúa todas y el genético evalúa hasta 96. El orden sugerido de cartas y las continuaciones se buscan con heurísticas. Después de cada robo, la estrategia evalúa candidatos de jugada y descarte y acciones de inventario sobre una observación independiente del futuro real. No enumera todas las secuencias ni todas las permutaciones de cartas o comodines. **El porcentaje no certifica el óptimo global**. El horizonte termina en esta ciega; no decide compras ni optimiza ciegas futuras, aunque el motor contiene las habilidades económicas correspondientes.

### Búsqueda genética

El modo genético usa una población de hasta 24 primeras acciones, iniciada con candidatos de jugada y descarte, acciones de inventario y exploración aleatoria. Mantiene un archivo de resultados para no repetir evaluaciones, conserva los mejores y genera hasta cuatro tandas más de 18 candidatos. Selecciona padres mediante torneos, cruza sus selecciones de cartas, muta cartas o tipos de acción y repara cada candidato contra las acciones legales disponibles. Usa hasta cinco generaciones y 96 evaluaciones; con menos de 96 opciones puede llegar a evaluarlas todas.

La calidad se mide con el mismo motor y las mismas muestras de Monte Carlo que en el modo clásico: mayor frecuencia estimada de ganar, luego menos manos entre victorias y los desempates de recursos descritos arriba. Se muestran las generaciones, las opciones evaluadas y el camino ganador. El genético busca la **primera acción**; las continuaciones siguen usando la estrategia aproximada existente y se adaptan a cada robo. No evoluciona una secuencia fija con conocimiento de los robos futuros ni el orden de comodines.

Evaluar menos candidatos puede reducir la espera, pero puede omitir la mejor primera acción. No corrige errores del modelo ni garantiza más victorias. La cantidad de tiradas y el algoritmo son controles independientes. Para contrastar una recomendación, elegí **Comparar todas** sobre la misma mano y recursos. El proceso sigue las operaciones habituales de [selección, cruce y mutación de los algoritmos evolutivos](https://deap.readthedocs.io/en/stable/api/algo.html), implementadas en Rust sin dependencias adicionales.

El simulador usa su propia semilla, independiente de la del juego, y muestras comunes entre las primeras acciones. La pila entra como composición canónica y se baraja para cada muestra. Las identidades ocultas se agrupan en una bolsa anónima y se reasignan en cada tirada; no se consulta la identidad de una posición oculta ni el orden futuro de robo. El orden de comodines ocultos también se muestrea. Las generaciones aleatorias respetan las cartas bloqueadas en el perfil cuando el mod actualizado exporta esa información.

## Interfaz y recálculo

El cálculo empieza solo al pulsar **Simular**. Durante el análisis aparecen resultados parciales a medida que cada opción termina las tiradas elegidas. Usa hasta ocho trabajadores. El modo rápido realiza 50 veces menos tiradas que el detallado; la duración depende de la mano y los recursos, y no se garantiza un tiempo fijo. El modo de 1000 puede tardar varios minutos. La barra mide opciones terminadas; cada resultado y registro conserva el número de tiradas que realmente utilizó. Cambiar el selector no altera un resultado anterior: se aplica al siguiente cálculo y queda bloqueado mientras se simula.

Las recomendaciones muestran cartas por valor y palo, por ejemplo **As ♠** o **J ♥**, y resaltan las cartas de la mano o del inventario. Seguí el orden mostrado cuando corresponda. Después de jugar, descartar, usar o vender, pulsá **Simular** de nuevo. Cualquier cambio relevante de estado cancela el cálculo anterior y retira su recomendación. El lector continúa respondiendo durante el cálculo.

La comparación usa los datos de juego que importa el motor: cartas y orden, recursos, valores de comodines, niveles, contadores y reglas de la ciega. Los temporizadores, movimientos de la interfaz, descripciones y vistas previas de manos no cancelan la simulación.

Seleccionar o deseleccionar cartas en Balatro conserva los detalles abiertos, el foco, el desplazamiento y los resultados del panel. Cada sección se actualiza cuando cambian sus datos visibles; las animaciones y ejemplos de manos no reconstruyen la interfaz. Los resultados terminados se conservan entre consultas y se retiran cuando la partida cambia de forma relevante.

## Identificar cartas dadas vuelta

Si hay cartas ocultas en la mano, aparece **¿Qué carta está dada vuelta?**:

1. En Balatro, pulsá **Categoría** y luego **Registrar Categoría** en el panel.
2. En Balatro, pulsá **Palo** y luego **Registrar Palo** en el panel.
3. Cada oculta conserva una letra al moverse. Consultá los valores, palos y dibujos de las cartas compatibles con ambos órdenes.

Las deducciones usan las cartas visibles y la posición de cada oculta en los órdenes descendentes estándar del juego. No leen el valor, palo ni mejora de la carta oculta y no usan la composición anónima del mazo para reducir las posibilidades. Admiten cartas repetidas y contemplan el orden especial de las cartas Piedra; una Piedra visible tampoco revela su valor o palo interno al identificador.

Se propagan los límites entre cartas hasta que dejan de cambiar. El resultado conserva todas las posibilidades factibles y puede conservar opciones adicionales cuando hay varias ocultas. No asigna porcentajes. Una única combinación es una deducción condicionada a haber registrado los órdenes correctos. La lista de cartas muestra las combinaciones reales del resultado; cruzar todos los valores con todos los palos de las filas puede producir combinaciones que no aparecen en esa lista.

Registrá después de pulsar el botón de ordenar del juego y de que las cartas terminen de moverse. Si las arrastraste manualmente, volvé a ordenar. Se rechazan órdenes incompatibles con las cartas visibles o con la otra observación. Los mods que cambian el orden estándar quedan fuera de este identificador.

Las observaciones se borran al jugar, descartar, usar un consumible, cambiar o revelar cartas, salir de la selección de mano o perder la conexión. **Borrar observaciones** permite empezar de nuevo. Se guardan con las capturas del lector; son temporales durante esa sesión y no se restauran al reiniciarlo. El simulador sigue usando su bolsa anónima y todavía no condiciona sus tiradas con estas pistas. Esta función solo registra la lectura y no pulsa botones ni juega cartas en Balatro.

## Builds y tienda

La sección **Qué aporta la tienda** incluye 12 builds investigadas en internet, con enlaces a sus fuentes, piezas presentes y piezas faltantes. Podés detectar una estrategia con tus comodines o elegir una build objetivo; la preferencia se conserva en el navegador.

Al entrar a la tienda, sus comodines y consumibles relacionados muestran un **índice de afinidad explicado** que considera compañeros, baraja, niveles y conflictos. El precio y los espacios se informan aparte. Este porcentaje mide compatibilidad heurística; la probabilidad de ganar una ciega sigue siendo la del botón **Simular**. Una carta sin relación revisada queda sin porcentaje. Consultá [BUILDS.md](BUILDS.md) para las combinaciones, la fórmula y los límites.

## Lectura y registro

La API se consulta cada segundo. Se guardan mano, pila de robo, descarte, colección, comodines, consumibles, niveles y usos de las manos, jefe activo y sus restricciones, historial de Tarot/planetas/espectrales, probabilidades y valores persistentes de cada carta.

- `registros/actual.json`: última captura con fecha UTC.
- `registros/historial.jsonl`: cambios observados.
- `registros/recomendacion.json`: último análisis terminado junto con su estado de entrada.
- `registros/recomendacion-parcial.json`: última recomendación provisional distinta junto con su estado de entrada, aunque después la partida interrumpa el cálculo. Permite revisar una estimación mostrada antes de llegar al resultado final.

Estos archivos permanecen en tu PC y se excluyen de Git. Una carta o jefe ajeno al registro del juego base bloquea la recomendación con su clave. No se admite contenido adicional de mods ni se garantiza fidelidad de desafíos con reglas especiales. El modelo recibe la situación de la ciega ya iniciada; no reproduce el inicio de una partida de cada baraja o apuesta.

## Desarrollo y pruebas

La API procede de [BalatroBot](https://github.com/coder/balatrobot), revisión fijada por el instalador. `integrations/gamestate.lua` amplía su lectura y se copia al mod instalado. Reiniciá Balatro después de actualizarla.

El motor Rust procede de [balatroagent](https://github.com/jahankazimi078/balatroagent), vendorizado bajo MIT. Su revisión, licencia y cambios locales se detallan en [engine/UPSTREAM.md](engine/UPSTREAM.md). La interfaz Python lanza un proceso aislado que recibe JSON, calcula y transmite resultados parciales; el motor no tiene acceso a la API del juego.

Con Rust estable y las herramientas de compilación de la plataforma:

```powershell
cargo test --manifest-path engine/Cargo.toml --workspace --release --locked
cargo build --manifest-path engine/Cargo.toml --release --locked
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest test_native_engine test_reader test_simulator test_synergies test_lua_snapshot test_hidden_cards -v
```

Las pruebas del núcleo cubren evaluación de manos, puntuación, comodines, jefes, consumibles, sellos, economía y aleatoriedad. Las pruebas de integración recorren los 150 comodines, 28 jefes y 52 consumibles y verifican importación de valores actuales, copias, eternos, restricciones, cartas ocultas, consumibles, descartes encadenados, resultados parciales y cancelación. GitHub ejecuta las pruebas en Windows y Linux. El evaluador anterior de Python queda como referencia de regresión; el panel utiliza el motor Rust.

## Licencia

Código del lector bajo MIT. El núcleo conserva [su licencia MIT](engine/vendor/balatro-core/LICENSE); la ampliación de BalatroBot conserva [su licencia](integrations/LICENSE-BalatroBot.txt). Lovely y Steamodded se descargan de sus proyectos oficiales. El repositorio y el motor no incluyen el juego, su código fuente ni sus imágenes, sonidos o archivos de guardado.

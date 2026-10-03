# Instalar en otra PC con Windows

La biblioteca de builds viene incluida en la descarga del repositorio. En el panel, buscá **Qué aporta la tienda**: elegí detección automática o una build objetivo. Las ofertas reciben afinidades al entrar a la tienda. Cada build muestra sus fuentes; la fórmula y su alcance están en [BUILDS.md](BUILDS.md).

## Requisitos

- Windows 10 u 11 de 64 bits.
- Una copia propia de Balatro instalada, preferentemente mediante Steam.
- Internet durante la instalación.
- `uv`, que descarga y prepara Python y las dependencias. No hace falta instalar Python o Git por separado.

## 1. Descargar este proyecto

En [el repositorio](https://github.com/sbernal1995/balatro-reader), elegí **Code → Download ZIP**. Extraé el ZIP en una carpeta de tu usuario, por ejemplo `C:\Juegos\balatro-reader`. También podés clonarlo si ya usás Git.

Extraé todos los archivos antes de ejecutar los accesos. Conservá la carpeta `integrations`: contiene la ampliación de la API que necesita el lector.

## 2. Instalar uv

Abrí PowerShell o Terminal y ejecutá:

```powershell
winget install --id astral-sh.uv --exact
```

Cerrá esa terminal y abrí una nueva. Comprobá que quedó disponible:

```powershell
uv --version
```

Si no tenés `winget`, consultá las alternativas de la [documentación oficial de uv](https://docs.astral.sh/uv/getting-started/installation/).

## 3. Preparar Balatro y el lector

Cerrá Balatro y hacé doble clic en **Instalar.cmd**. El instalador:

1. Busca el juego en las bibliotecas de Steam.
2. Descarga el motor de reglas para Windows de 64 bits y verifica su SHA-256. No hace falta instalar Rust ni un compilador.
3. Prepara Python 3.13 y las dependencias dentro del proyecto.
4. Descarga Lovely 0.10.0, Steamodded 26.1002.0 y una versión fijada de BalatroBot.
5. Instala los mods y copia la ampliación que permite leer la baraja completa, el uso de consumibles y los valores de los comodines.
6. Guarda la ruta de tu juego en `config.local.json`.

Si el juego está en una carpeta que no se detecta, abrí una terminal dentro de la carpeta del proyecto y ejecutá, reemplazando la ruta por la tuya:

```powershell
.\Instalar.cmd -BalatroPath "D:\SteamLibrary\steamapps\common\Balatro"
```

La ruta debe ser la carpeta que contiene `Balatro.exe`. El instalador crea respaldos de mods existentes y de `winmm.dll` dentro de `.downloads`. No incluye el juego ni modifica sus archivos de guardado.

Si Windows informa que no se puede escribir en el directorio del juego, ejecutá **Instalar.cmd** como administrador. Los logros se configuran como **Enabled**, con las restricciones normales; no se activa **Bypass Restrictions**. Si ya tenías una configuración guardada de Steamodded, comprobá esa opción en su menú de configuración.

## 4. Abrir y usar

Hacé doble clic en **Iniciar.cmd**. Se abre Balatro con la API y el panel en [http://127.0.0.1:8765](http://127.0.0.1:8765).

1. Empezá o continuá una partida.
2. Con las cartas en la mano, pulsá **Simular**.
3. Mirá los resultados parciales y esperá la recomendación final. Las cartas se muestran por valor y palo, por ejemplo **As ♠** o **J ♥**.
4. Jugá, descartá, usá o vendé la carta indicada en Balatro. Cuando cambia el estado, la recomendación anterior se retira.
5. Pulsá **Simular** nuevamente para calcular con las cartas reales, las fichas que faltan y las manos y descartes restantes.

Cuando tengas cartas dadas vuelta, aparece **¿Qué carta está dada vuelta?** debajo de la mano. Pulsá **Categoría** en Balatro y **Registrar Categoría** en el panel; repetí con **Palo** y **Registrar Palo**. Las cartas ocultas conservan una letra al moverse y muestran valores, palos y cartas dibujadas compatibles con esos órdenes. Ordená de nuevo si arrastraste cartas manualmente. Las pistas se borran al cambiar la mano o realizar una acción y todavía no condicionan las tiradas del simulador.

El cálculo compara jugar, descartar, usar consumibles y vender cartas con todas las manos y descartes restantes. Empieza en **modo rápido: 20 rondas simuladas por opción**. Podés elegir 100 o 1000 en el selector antes de pulsar **Simular**; más tiradas requieren más tiempo y estabilizan el muestreo. Incorpora los **150 comodines, 28 ciegas jefe y 52 consumibles**, mejoras, ediciones y sellos. Usa los niveles, probabilidades, contadores y habilidades actuales. Prioriza ganar la ciega y luego necesitar menos manos. Las continuaciones son aproximadas; el porcentaje no garantiza el óptimo global. El modo rápido es orientativo y puede cambiar el ranking con pocas tiradas; el detallado puede tardar varios minutos. Consultá [README.md](README.md) para conocer el alcance.

Para usar la API, abrí el juego mediante **Iniciar.cmd**. Si ya lo abriste desde Steam sin la API, cerralo y usá ese acceso. Podés cerrar el panel sin detener el lector; para terminar por completo, cerrá Balatro y los procesos del lector en el Administrador de tareas.

## Archivos que se guardan localmente

- `registros/actual.json`: última captura del juego.
- `registros/historial.jsonl`: historial de cambios observados.
- `registros/recomendacion.json`: último análisis finalizado y el estado utilizado.
- `registros/recomendacion-parcial.json`: última recomendación provisional distinta y el estado utilizado, para revisar estimaciones de cálculos interrumpidos.
- `reader.log` y `reader-error.log`: registros del lector.
- `game.log`, `game-error.log` y `logs/`: registros de la API y el juego.

Estos archivos, la configuración local y las dependencias se excluyen del repositorio. Cada instalación mantiene sus propios registros.

## Resolver problemas

| Situación | Qué hacer |
| --- | --- |
| `uv` no se reconoce | Instalalo y abrí una terminal nueva. |
| No se encuentra Balatro | Usá `-BalatroPath` con la carpeta del juego. |
| Sin conexión en el panel | Cerrá Balatro y volvé a abrirlo con `Iniciar.cmd`. Revisá `game-error.log` y `reader-error.log` si persiste. |
| Faltan baraja o contadores internos | Ejecutá `Instalar.cmd` con el juego cerrado y volvé a abrirlo. |
| No aparece una recomendación | Leé el motivo del panel. Actualizá el mod si falta la clave del jefe o el contexto; las cartas de mods adicionales no están admitidas. |
| Falta el motor o la descarga no coincide | Descargá el proyecto actualizado y volvé a ejecutar `Instalar.cmd`. |
| El cálculo se interrumpe | La partida cambió durante la simulación. Pulsá **Simular** otra vez. |
| Los puertos están ocupados | Cerrá la otra instancia del lector o el programa que ocupa 8765 o 12346. |

## Actualizar

Descargá la nueva versión o ejecutá `git pull` si clonaste el repositorio. Conservá tus registros si querés mantenerlos. Con Balatro cerrado, volvé a ejecutar **Instalar.cmd** y luego **Iniciar.cmd**.

## Verificar las pruebas

Después de instalar, desde la carpeta del proyecto:

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest test_native_engine test_simulator test_reader test_synergies test_lua_snapshot test_hidden_cards -v
```

Para desarrollo, `Instalar.cmd -SkipModInstall` prepara las dependencias y detecta el juego sin reinstalar los mods. El instalador y el lanzador están preparados para Windows; no incluyen un flujo de instalación para macOS o Linux.


El motor compilado se publica en [Releases](https://github.com/sbernal1995/balatro-reader/releases). El instalador usa la versión fijada y el SHA-256 de `Instalar.ps1`. Para modificar el motor necesitás Rust estable y Visual Studio Build Tools con C++ en Windows; las instrucciones de compilación están en README.md.

# Ampliación de BalatroBot

`gamestate.lua` deriva de [coder/balatrobot](https://github.com/coder/balatrobot), commit `e7c6db8a9ad88318f6e4128eefd6e61aafc94885`, bajo licencia MIT. La licencia original se conserva en `LICENSE-BalatroBot.txt`.

Cambios de este proyecto:

- `collection`: colección completa de cartas, ordenada por identificador.
- `joker_context`: contadores de consumibles, manos, descartes, probabilidades y contexto de ronda.
- `ability` y `runtime`: valores actuales de las cartas y de los comodines.
- Copia de datos serializables con límite de profundidad y protección ante referencias circulares.

El instalador descarga la versión fijada de BalatroBot y reemplaza este archivo tanto en la copia local de la dependencia como en el mod instalado. No se distribuye código ni archivos de Balatro en este repositorio.

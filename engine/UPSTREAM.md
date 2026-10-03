# Motor de reglas

`vendor/balatro-core` procede de [jahankazimi078/balatroagent](https://github.com/jahankazimi078/balatroagent), revisión `38ae214317009952db4d22a98dc0765cef79370a`, bajo licencia MIT. Se conservan su licencia y pruebas. Incluye 150 comodines, 28 jefes, 52 consumibles y las reglas de mejoras, ediciones y sellos del juego base. El recuento de consumibles se obtiene del registro compilado, no de la descripción del repositorio.

La integración añade importación del estado del lector, búsqueda Monte Carlo y adaptación de la observación. No distribuye código, imágenes, sonidos ni archivos extraídos de Balatro.

Cambios al núcleo vendorizado: puntuación Plasma; tamaño inicial de baraja importado para Erosion; generación de comodines restringida al perfil real; conservación de eternos en Ankh/Hex; importación de alquiler/perecederos, valor de venta y cierre de ronda de sus pegatinas; reasignación de cartas y comodines ocultos, actualización de debilidades y ordenación privada de cartas seleccionadas. Los campos adicionales tienen valores por defecto para conservar compatibilidad con las pruebas y capturas originales.

# Tablero QA — Matriz de Casos de Prueba (Copetran 360)

Tablero en vivo de la Matriz de Casos de Prueba con base de datos **SQLite**
(historial de cambios de estado + snapshots por área) y vista por áreas,
responsables y tipos de novedad.

## Cómo funciona

- **`index.html`** — el tablero. Parsea el Excel de la matriz en el navegador
  (botón «📂 Excel local» o arrastrando el .xlsx) y lo empuja al servidor.
- **`servidor.py`** — servidor (solo librería estándar de Python). Guarda todo
  en `matriz_qa.db`: casos (upsert), historial de cambios de estado, snapshots
  por área y registro de cargas. Sirve el tablero y una API JSON.
- Quien abre el tablero **no necesita el Excel**: ve lo que está en la base.
  Si el servidor no está disponible, el tablero funciona en modo autónomo.

## Uso local / oficina

Doble clic en `INICIAR_TABLERO.bat` (o `python servidor.py`). Queda en
`http://127.0.0.1:8765` y para la red local en `http://<ip-del-pc>:8765`
(abrir el puerto: `netsh advfirewall firewall add rule name="Tablero QA"
dir=in action=allow protocol=TCP localport=8765`).

## Despliegue gratis en Render (para acceso desde internet)

1. Entrar a [render.com](https://render.com) e iniciar sesión con GitHub.
2. **New → Web Service** → elegir este repositorio (`Matrizcarga360`).
3. Render lee `render.yaml` automáticamente (plan **Free**). Si pide datos:
   runtime *Python*, start command `python servidor.py --no-abrir`.
4. (Recomendado) En *Environment* definir `TABLERO_TOKEN` con una clave
   cualquiera: los espectadores ven todo, pero solo quien tenga el token
   puede subir datos (el tablero lo pide una sola vez y lo recuerda).
5. Abrir la URL que entrega Render (`https://tablero-qa-XXXX.onrender.com`),
   conectar el Excel con «📂 Excel local» una vez, y compartir la URL.

Notas del plan gratuito: el servicio **se duerme tras ~15 min sin visitas**
(la primera visita después tarda ~1 min en despertar) y el disco es efímero —
si Render reinicia, la base se vacía, pero el tablero la **repuebla solo**
en cuanto quien tiene el Excel conectado vuelva a abrir la página (el
historial de snapshots sí se pierde). Para historial permanente: correrlo en
la oficina o usar un plan con disco persistente.

## API

- `GET /api/estado` — salud y última carga
- `GET /api/datos` — casos activos + pruebas OK
- `GET /api/historia?dias=90` — snapshots globales (tendencia medida)
- `POST /api/cargar` — upsert de casos (exige `X-Token` si `TABLERO_TOKEN` está definido)
- `GET /db` — descarga la base `matriz_qa.db` para compartir/respaldar

## Nota

El vínculo de SharePoint del Excel exige inicio de sesión (no es anónimo),
por eso la fuente es el Excel local. Si TIC crea un vínculo "Cualquier
persona con el vínculo", pegarlo en `CONFIG.SHARE_LINK` de `index.html` y el
tablero se alimentará solo, sin archivo local.

# Tablero QA — Matriz de Casos de Prueba (Copetran 360)

Página **100 % estática**: HTML + JavaScript, sin servidor, sin Python y sin
base de datos. Se publica tal cual en **GitHub Pages** y funciona desde
cualquier equipo de la oficina.

```
index.html          el tablero completo (todo el código está aquí)
vendor/             SheetJS y Chart.js servidos desde el repo (sin CDN externo)
herramientas/       generador opcional de datos.json por línea de comandos
.nojekyll           para que GitHub Pages publique la carpeta tal cual
_legacy-python/     el servidor Python y la BD SQLite anteriores (ya no se usan)
```

## Publicarlo en GitHub Pages

1. Sube esta carpeta a un repositorio.
2. **Settings → Pages → Source: Deploy from a branch**, rama `main`, carpeta `/ (root)`.
3. Listo. La dirección queda como `https://<usuario>.github.io/<repo>/`.

No hay nada que instalar ni que dejar corriendo.

## Los datos NO están en este repositorio

Este repo es **público** y GitHub Pages no pide contraseña, así que la matriz de
Copetran (descripciones de fallos, responsables, fechas) **no se sube**:
`datos.json` está en el `.gitignore` a propósito.

Para usar el tablero, abre la página y conecta el Excel con **📂 Excel local**
(o arrastra el `.xlsx` encima). Los datos se quedan en tu equipo.

> Si algún día quieres que la oficina lo vea sin tener el Excel, quita
> `datos.json` del `.gitignore` y súbelo — pero ten en cuenta que entonces
> queda visible para cualquiera en internet. La alternativa es repo privado +
> GitHub Pages, que exige cuenta Pro/Team.

## Cómo se actualizan los datos

El tablero lee, en este orden:

1. **El Excel de tu equipo**, si lo conectas con **📂 Excel local**. Se relee
   solo cada minuto: si guardas el Excel, el tablero se actualiza.
2. **`datos.json`**, si decides publicarlo en el repositorio — sería lo que
   vería todo el que abra la dirección de GitHub Pages (hoy no está subido).
3. **`matriz.xlsx`**, si prefieres subir el Excel crudo al repositorio.

### Si decides publicar los datos

1. Abre el tablero y conecta el Excel con **📂 Excel local**.
2. Pulsa **⬆ Publicar**: se descarga un `datos.json`.
3. Sube ese `datos.json` a la raíz del repositorio (reemplazando el anterior).

También puedes generarlo desde la terminal, sin abrir el navegador:

```bash
node herramientas/generar-datos.mjs "Matriz de Casos de Prueba.xlsx"
```

Esa herramienta **no duplica la lógica**: extrae el parser del propio
`index.html`, así que nunca puede quedar desincronizada del tablero.

## Cómo se calcula el avance

La matriz lleva **dos estados por caso** y hay que mirar los dos:

| Columna del Excel | Quién la llena | Qué significa |
|---|---|---|
| `ESTADO DE NOVEDAD` | Copetran | reporta la novedad y, al final, la valida |
| `ESTADO DE CORRECCIÓN PRISS` | PRISS | corrige y entrega |

De ahí salen cinco estados:

| Estado | Cuándo | De quién es la pelota |
|---|---|---|
| **PENDIENTE** | reportada, PRISS no ha respondido | PRISS |
| **EN PROCESO** | PRISS: `EN DESARROLLO` | PRISS |
| **ESPERA INFO** | PRISS: `PENDIENTE INFORMACIÓN` | Copetran |
| **POR VALIDAR** | PRISS: `RESUELTA`, Copetran aún no valida | Copetran |
| **RESUELTO** | Copetran: `RESUELTA` | cerrado |

Y dos porcentajes, porque no son lo mismo:

- **Entregado** = (POR VALIDAR + RESUELTO) / total — lo que PRISS ya sacó.
- **Validado** = RESUELTO / total — lo que Copetran ya dio por bueno.

El anillo muestra los dos: el arco tenue es lo entregado, el sólido lo validado.
La diferencia entre ambos es el trabajo entregado que espera validación.

> El anillo **no** se recalcula con el filtro de Estado: si lo hiciera, elegir
> «Sin atender» dejaría el avance en 0 % por definición.

## Filtros

Los cinco filtros de la barra superior — **Responsable, Área, Módulo, Tipo y
Estado** — mandan sobre **todo** el tablero: Panorama y Tareas por igual. Se
guardan en el navegador, así que sobreviven a un F5.

Los chips de cada tarjeta de área (`falta entregar: …`) cuentan **solo lo que
PRISS todavía no ha entregado**. Por eso un área sin errores por entregar deja
de mostrar «ERROR».

## Avisos que puede dar el tablero

- **«No se pudieron leer estas hojas»** — una hoja del Excel no se pudo abrir.
  Casi siempre es porque tiene formato aplicado a un millón de filas vacías:
  ábrela, selecciona las filas sobrantes, bórralas y vuelve a guardar.
- **«N sin clasificar en la matriz»** — filas con un hallazgo escrito en
  OBSERVACIONES a las que nadie les puso tipo ni estado. Aparecen como
  `SIN CLASIFICAR` para que no se pierdan.
- **«N entregas sin fecha»** — casos entregados sin `FECHA DE CORRECCIÓN`: no
  se pueden medir, y por eso el promedio de días dice sobre cuántos casos está
  calculado.
- **«N casos sin responsable quedan fuera»** — al filtrar por responsable, las
  filas sin `RESPONSABLE` en el Excel desaparecerían sin avisar.

## Requisitos del navegador

Cualquier navegador moderno. Conectar el Excel local usa la File System Access
API (Chrome/Edge); en el resto funciona igual con el selector de archivos o
arrastrando el `.xlsx` a la página.

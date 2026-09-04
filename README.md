# Tablero QA — Matriz de Casos de Prueba (Copetran 360)

Página **100 % estática**: HTML + JavaScript, sin servidor, sin Python y sin
base de datos. Se publica tal cual en **GitHub Pages** y funciona desde
cualquier equipo de la oficina.

```
index.html          el tablero completo (todo el código está aquí)
datos.json          la foto de la matriz que ve la oficina   ← esto se actualiza
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

## Actualizar el tablero para toda la oficina

Tú cargas el Excel, publicas, y todos ven lo mismo. Un solo comando:

```bash
node herramientas/publicar.mjs "Matriz de Casos de Prueba.xlsx"
```

(o doble clic en **`PUBLICAR.bat`**, que hace lo mismo)

Regenera `datos.json` desde el Excel y lo sube al repositorio. GitHub Pages se
actualiza solo en un par de minutos y el tablero de todos muestra los datos
nuevos — nadie más necesita el Excel.

Si prefieres no usar la terminal: pulsa **⬆ Publicar** en el tablero, se te
descarga un `datos.json`, y lo arrastras a la página del repositorio en GitHub
(*Add file → Upload files*) reemplazando el anterior.

> Ten presente que el repositorio es **público**: cualquiera con la dirección ve
> la matriz. Si eso no sirve, la alternativa es repo privado + GitHub Pages,
> que exige cuenta Pro/Team.

## Cómo se actualizan los datos

El tablero lee, en este orden:

1. **El Excel que cargues** con **📂 Cargar Excel** (o arrastrándolo a la
   página). Vale solo para esa pestaña: al recargar se vuelve a lo publicado.
2. **`datos.json`** publicado en el repositorio — esto es lo que ve todo el que
   abra la dirección de GitHub Pages.
3. **`matriz.xlsx`**, si prefieres subir el Excel crudo al repositorio.

`herramientas/generar-datos.mjs` solo regenera el archivo, sin subirlo;
`herramientas/publicar.mjs` lo regenera **y** lo sube. Ninguna de las dos
duplica la lógica: extraen el parser del propio `index.html`, así que nunca
pueden quedar desincronizadas del tablero.

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

Cualquier navegador moderno. El Excel se elige con el selector de archivos o
arrastrándolo a la página; no se usa ninguna API especial.

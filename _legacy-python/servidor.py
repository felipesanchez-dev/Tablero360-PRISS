#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor local del Tablero QA (Copetran 360) — solo librería estándar.

- Guarda la Matriz de Casos de Prueba en SQLite (matriz_qa.db, junto a este archivo).
- El tablero (index.html) parsea el Excel en el navegador y lo empuja aquí
  vía POST /api/cargar; el servidor hace upsert, registra el historial de
  cambios de estado (tabla eventos) y toma snapshots por área (tabla snapshots)
  para tendencias reales medidas en el tiempo.
- Sirve el tablero en http://127.0.0.1:8765 y para toda la oficina en
  http://<ip-de-este-pc>:8765 (los demás no necesitan el Excel).
- La base de datos es un archivo normal: se puede copiar, respaldar o compartir.

Uso:  python servidor.py            (abre el navegador solo)
      python servidor.py --no-abrir
"""
import json
import hashlib
import os
import sqlite3
import sys
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "matriz_qa.db"
INDEX = BASE / "index.html"
PUERTO = int(os.environ.get("PORT", 8765))  # hosting (Render, etc.) define PORT
# Si TABLERO_TOKEN está definido, POST /api/cargar exige ese token (header X-Token).
# Recomendado al exponer el servidor a internet.
TOKEN_CARGA = os.environ.get("TABLERO_TOKEN") or None
SNAPSHOT_MAX_EDAD_SEG = 3600  # snapshot aunque no haya cambios si el último es más viejo que esto

CAMPOS = ("a", "n", "p", "t", "r", "e", "fp", "fc", "o")


def ahora():
    return datetime.now().isoformat(timespec="seconds")


def conectar():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db():
    with conectar() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS casos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clave TEXT UNIQUE NOT NULL,
                a  TEXT, n TEXT, p TEXT, t TEXT, r TEXT,
                e  TEXT, fp TEXT, fc TEXT, o TEXT,
                activo INTEGER NOT NULL DEFAULT 1,
                creado_en TEXT NOT NULL,
                actualizado_en TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clave TEXT NOT NULL,
                campo TEXT NOT NULL,
                de TEXT, a TEXT,
                ts TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS snapshots (
                ts TEXT NOT NULL,
                area TEXT NOT NULL,           -- '*' = global
                total INTEGER, resueltos INTEGER,
                en_proceso INTEGER, pendientes INTEGER,
                pruebas_ok INTEGER            -- solo en la fila global
            );
            CREATE TABLE IF NOT EXISTS cargas (
                ts TEXT NOT NULL,
                origen TEXT,
                casos INTEGER,
                cambios INTEGER
            );
            CREATE TABLE IF NOT EXISTS kv (
                k TEXT PRIMARY KEY,
                v TEXT
            );
            CREATE INDEX IF NOT EXISTS ix_eventos_clave ON eventos(clave);
            CREATE INDEX IF NOT EXISTS ix_snapshots_ts ON snapshots(ts);
            """
        )


def clave_de(c):
    base = f"{c.get('a') or ''}|{c.get('n') or ''}|{c.get('p') or ''}"
    if not c.get("n"):  # sin número de caso: distinguir por la observación
        base += "|" + hashlib.md5((c.get("o") or "").encode("utf-8")).hexdigest()[:8]
    return base


def _conteos(filas):
    tot = len(filas)
    res = sum(1 for f in filas if f["e"] == "RESUELTO")
    pro = sum(1 for f in filas if f["e"] == "EN PROCESO")
    return tot, res, pro, tot - res - pro


def cargar_casos(payload):
    casos = payload.get("casos") or []
    origen = str(payload.get("origen") or "?")[:200]
    ts = ahora()
    nuevos = cambios = desactivados = 0

    with conectar() as con:
        activos_previos = {
            r["clave"] for r in con.execute("SELECT clave FROM casos WHERE activo=1")
        }
        vistos = set()
        for c in casos:
            k = clave_de(c)
            if k in vistos:  # fila duplicada en el Excel: conservar la primera
                continue
            vistos.add(k)
            fila = con.execute("SELECT * FROM casos WHERE clave=?", (k,)).fetchone()
            valores = {campo: (c.get(campo) or None) for campo in CAMPOS}
            if fila is None:
                con.execute(
                    "INSERT INTO casos (clave,a,n,p,t,r,e,fp,fc,o,activo,creado_en,actualizado_en)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?)",
                    (k, *[valores[x] for x in CAMPOS], ts, ts),
                )
                con.execute(
                    "INSERT INTO eventos (clave,campo,de,a,ts) VALUES (?,?,?,?,?)",
                    (k, "nuevo", None, valores["e"], ts),
                )
                nuevos += 1
                continue
            difs = {x: valores[x] for x in CAMPOS if (fila[x] or None) != valores[x]}
            reactivar = fila["activo"] == 0
            if difs or reactivar:
                sets = ", ".join(f"{x}=?" for x in difs)
                params = list(difs.values())
                if reactivar:
                    sets = (sets + ", " if sets else "") + "activo=1"
                con.execute(
                    f"UPDATE casos SET {sets}, actualizado_en=? WHERE clave=?",
                    (*params, ts, k),
                )
                if "e" in difs:  # historial de cambios de estado
                    con.execute(
                        "INSERT INTO eventos (clave,campo,de,a,ts) VALUES (?,?,?,?,?)",
                        (k, "estado", fila["e"], difs["e"], ts),
                    )
                cambios += 1

        for k in activos_previos - vistos:
            con.execute(
                "UPDATE casos SET activo=0, actualizado_en=? WHERE clave=?", (ts, k)
            )
            con.execute(
                "INSERT INTO eventos (clave,campo,de,a,ts) VALUES (?,?,?,?,?)",
                (k, "retirado", None, None, ts),
            )
            desactivados += 1

        if payload.get("pruebasOk") is not None:
            con.execute(
                "INSERT INTO kv (k,v) VALUES ('pruebas_ok',?)"
                " ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (str(int(payload["pruebasOk"])),),
            )

        total_cambios = nuevos + cambios + desactivados
        con.execute(
            "INSERT INTO cargas (ts,origen,casos,cambios) VALUES (?,?,?,?)",
            (ts, origen, len(casos), total_cambios),
        )

        # Snapshot si hubo cambios, o si el último ya está viejo
        ult = con.execute("SELECT MAX(ts) m FROM snapshots").fetchone()["m"]
        viejo = (
            ult is None
            or (datetime.fromisoformat(ts) - datetime.fromisoformat(ult)).total_seconds()
            > SNAPSHOT_MAX_EDAD_SEG
        )
        if total_cambios > 0 or viejo:
            filas = con.execute(
                "SELECT a,e FROM casos WHERE activo=1"
            ).fetchall()
            p_ok = con.execute("SELECT v FROM kv WHERE k='pruebas_ok'").fetchone()
            tot, res, pro, pen = _conteos(filas)
            con.execute(
                "INSERT INTO snapshots (ts,area,total,resueltos,en_proceso,pendientes,pruebas_ok)"
                " VALUES (?,?,?,?,?,?,?)",
                (ts, "*", tot, res, pro, pen, int(p_ok["v"]) if p_ok else None),
            )
            for area in sorted({f["a"] or "—" for f in filas}):
                sub = [f for f in filas if (f["a"] or "—") == area]
                tot, res, pro, pen = _conteos(sub)
                con.execute(
                    "INSERT INTO snapshots (ts,area,total,resueltos,en_proceso,pendientes)"
                    " VALUES (?,?,?,?,?,?)",
                    (ts, area, tot, res, pro, pen),
                )

        total_activos = con.execute(
            "SELECT COUNT(*) c FROM casos WHERE activo=1"
        ).fetchone()["c"]

    return {
        "ok": True,
        "nuevos": nuevos,
        "cambios": cambios,
        "desactivados": desactivados,
        "total": total_activos,
        "ts": ts,
    }


def obtener_datos():
    with conectar() as con:
        casos = [
            {x: r[x] for x in CAMPOS}
            for r in con.execute(
                "SELECT * FROM casos WHERE activo=1 ORDER BY a, n"
            )
        ]
        p_ok = con.execute("SELECT v FROM kv WHERE k='pruebas_ok'").fetchone()
        carga = con.execute(
            "SELECT ts,origen,casos,cambios FROM cargas ORDER BY ts DESC, rowid DESC LIMIT 1"
        ).fetchone()
        historico = con.execute("SELECT COUNT(*) c FROM casos").fetchone()["c"]
    return {
        "casos": casos,
        "pruebasOk": int(p_ok["v"]) if p_ok else 0,
        "ultimaCarga": dict(carga) if carga else None,
        "totalHistorico": historico,
    }


def obtener_historia(dias):
    corte = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
    with conectar() as con:
        global_ = [
            dict(r)
            for r in con.execute(
                "SELECT ts,total,resueltos,en_proceso,pendientes FROM snapshots"
                " WHERE area='*' AND ts>=? ORDER BY ts",
                (corte,),
            )
        ]
    return {"global": global_}


def obtener_estado():
    with conectar() as con:
        total = con.execute("SELECT COUNT(*) c FROM casos WHERE activo=1").fetchone()["c"]
        carga = con.execute(
            "SELECT ts,origen FROM cargas ORDER BY ts DESC, rowid DESC LIMIT 1"
        ).fetchone()
    return {
        "ok": True,
        "servicio": "tablero-qa",
        "casos": total,
        "ultimaCarga": dict(carga) if carga else None,
        "db": DB_PATH.name,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "TableroQA/1.0"
    protocol_version = "HTTP/1.1"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Token")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _json(self, obj, code=200):
        cuerpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _archivo(self, ruta, mime, descarga=None):
        try:
            datos = ruta.read_bytes()
        except FileNotFoundError:
            return self._json({"ok": False, "error": f"No existe {ruta.name}"}, 404)
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        if descarga:
            self.send_header(
                "Content-Disposition", f'attachment; filename="{descarga}"'
            )
        self.end_headers()
        self.wfile.write(datos)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self):  # sondas de salud de los proxies (Render, etc.)
        self.send_response(200)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        try:
            if url.path in ("/", "/index.html"):
                return self._archivo(INDEX, "text/html; charset=utf-8")
            if url.path == "/api/estado":
                return self._json(obtener_estado())
            if url.path == "/api/datos":
                return self._json(obtener_datos())
            if url.path == "/api/historia":
                dias = int(parse_qs(url.query).get("dias", ["90"])[0])
                return self._json(obtener_historia(max(1, min(dias, 3650))))
            if url.path == "/db":  # descargar/compartir la base de datos
                return self._archivo(
                    DB_PATH, "application/octet-stream", descarga="matriz_qa.db"
                )
            return self._json({"ok": False, "error": "Ruta no encontrada"}, 404)
        except Exception as e:  # noqa: BLE001 — el servidor no debe caerse
            return self._json({"ok": False, "error": str(e)}, 500)

    def do_POST(self):
        url = urlparse(self.path)
        try:
            if url.path == "/api/cargar":
                if TOKEN_CARGA and self.headers.get("X-Token") != TOKEN_CARGA:
                    return self._json(
                        {"ok": False, "error": "Token de carga inválido"}, 401
                    )
                largo = int(self.headers.get("Content-Length") or 0)
                if largo <= 0 or largo > 100 * 1024 * 1024:
                    return self._json({"ok": False, "error": "Cuerpo inválido"}, 400)
                payload = json.loads(self.rfile.read(largo).decode("utf-8"))
                return self._json(cargar_casos(payload))
            return self._json({"ok": False, "error": "Ruta no encontrada"}, 404)
        except json.JSONDecodeError:
            return self._json({"ok": False, "error": "JSON inválido"}, 400)
        except Exception as e:  # noqa: BLE001
            return self._json({"ok": False, "error": str(e)}, 500)

    def log_message(self, fmt, *args):  # silenciar GETs de sondeo; dejar el resto
        try:
            msg = fmt % args  # args puede traer HTTPStatus u otros no-str
        except Exception:  # noqa: BLE001
            msg = str(fmt)
        if "/api/estado" not in msg:
            sys.stderr.write("%s - %s\n" % (self.address_string(), msg))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    init_db()
    srv = ThreadingHTTPServer(("0.0.0.0", PUERTO), Handler)
    print(f"Tablero QA con base de datos SQLite: {DB_PATH}")
    print(f"  Local:   http://127.0.0.1:{PUERTO}")
    print(f"  Oficina: http://<ip-de-este-pc>:{PUERTO}   (mismo tablero, sin Excel)")
    print(f"  Copia de la BD para compartir: http://127.0.0.1:{PUERTO}/db")
    if TOKEN_CARGA:
        print("Token de carga ACTIVO (POST /api/cargar exige X-Token).")
    print("Ctrl+C para detener.")
    if "--no-abrir" not in sys.argv and not os.environ.get("PORT"):
        webbrowser.open(f"http://127.0.0.1:{PUERTO}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")


if __name__ == "__main__":
    main()

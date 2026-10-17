from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from functools import lru_cache
import os
from uuid import uuid4

from flask import Flask, redirect, render_template_string, request
from azure.data.tables import TableClient
from azure.identity import DefaultAzureCredential

app = Flask(__name__)

PAGINA = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Calculadora de presupuesto</title>
    <style>
        body {
            font-family: system-ui, sans-serif;
            background: #f1f5f9;
            color: #172033;
            margin: 0;
            padding: 48px 20px;
        }
        main {
            max-width: 520px;
            margin: auto;
            padding: 32px;
            background: white;
            border-radius: 16px;
            box-shadow: 0 8px 30px #17203312;
        }
        h1 { margin-top: 0; }
        label { display: block; margin-top: 20px; }
        input, button {
            box-sizing: border-box;
            width: 100%;
            padding: 12px;
            margin-top: 8px;
            border-radius: 8px;
            font: inherit;
        }
        input { border: 1px solid #94a3b8; }
        button {
            margin-top: 24px;
            background: #175cd3;
            color: white;
            border: 0;
            cursor: pointer;
        }
        .resultado {
            margin-top: 24px;
            padding: 16px;
            background: #eaf2ff;
            border-radius: 8px;
        }
        .error { color: #b42318; }
        footer { margin-top: 28px; color: #64748b; font-size: 14px; }
    </style>
</head>
<body>
<main>
    <h1>Calculadora de presupuesto</h1>
    <p>Calcula el coste de una suscripción para tu equipo.</p>

    <form method="post">
        <label for="usuarios">Número de usuarios</label>
        <input id="usuarios" name="usuarios" type="number"
               min="1" max="1000000" step="1" required
               value="{{ usuarios }}">

        <label for="precio">Precio mensual por usuario (€)</label>
        <input id="precio" name="precio" type="number"
               min="0" max="1000000" step="0.01" required
               value="{{ precio }}">

        <button type="submit">Calcular presupuesto</button>
    </form>

    {% if error %}
        <p class="error" role="alert">{{ error }}</p>
    {% endif %}

    {% if mensual is not none %}
        <section class="resultado" aria-live="polite">
            <p><strong>Coste mensual:</strong> {{ mensual }} €</p>
            <p><strong>Coste anual:</strong> {{ anual }} €</p>
        </section>
        {% if autenticado %}
            <form method="post" action="/guardar">
                <input type="hidden" name="usuarios" value="{{ usuarios }}">
                <input type="hidden" name="precio" value="{{ precio }}">
                <button type="submit">Guardar en mi historial</button>
            </form>
        {% else %}
            <p><a href="/.auth/login/aad?post_login_redirect_uri=/">
                Inicia sesión con Microsoft para guardar presupuestos
            </a>. Después, vuelve a calcularlo.
            </p>
        {% endif %}
    {% endif %}

    {% if autenticado %}
        <p><a href="/privado">Ver mi historial de presupuestos</a></p>
    {% else %}
        <p><a href="/privado">Iniciar sesión y abrir mi historial</a></p>
    {% endif %}
    <footer>Proyecto de portfolio · Python + Flask + Microsoft Entra ID</footer>
</main>
</body>
</html>
"""

PAGINA_PRIVADA = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Mis presupuestos</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #f1f5f9; color: #172033; margin: 0; padding: 48px 20px; }
        main { max-width: 720px; margin: auto; padding: 32px; background: white; border-radius: 16px; box-shadow: 0 8px 30px #17203312; }
        li { margin: 16px 0; padding: 16px; background: #f8fafc; border-radius: 8px; }
        button { padding: 8px 12px; border: 0; border-radius: 6px; background: #b42318; color: white; cursor: pointer; }
        .error { color: #b42318; }
    </style>
</head>
<body>
<main>
    <h1>Mis presupuestos</h1>
    <p>Sesión iniciada como <strong>{{ nombre }}</strong>.</p>
    {% if error %}<p class="error" role="alert">{{ error }}</p>{% endif %}
    {% if presupuestos %}
        <ul>
        {% for p in presupuestos %}
            <li>
                <strong>{{ p.created_at }}</strong><br>
                {{ p.usuarios }} usuarios × {{ p.precio }} € al mes<br>
                Coste mensual: {{ p.mensual }} € · Coste anual: {{ p.anual }} €
                <form method="post" action="/eliminar/{{ p.row_key }}">
                    <button type="submit">Eliminar</button>
                </form>
            </li>
        {% endfor %}
        </ul>
    {% else %}
        <p>Aún no has guardado presupuestos. Calcula uno y pulsa «Guardar en mi historial».</p>
    {% endif %}
    <p><a href="/">Volver a la calculadora</a></p>
    <p><a href="/.auth/logout?post_logout_redirect_uri=/">Cerrar sesión</a></p>
</main>
</body>
</html>
"""

TABLE_NAME = "presupuestoHistorial"


@lru_cache(maxsize=1)
def get_budget_table():
    endpoint = os.environ.get("AZURE_TABLES_ENDPOINT")
    if not endpoint:
        raise RuntimeError("Falta configurar AZURE_TABLES_ENDPOINT en App Service.")

    return TableClient(
        endpoint=endpoint,
        table_name=TABLE_NAME,
        credential=DefaultAzureCredential(),
    )


def authenticated_user():
    # App Service Authentication (Easy Auth) adds these headers after sign-in.
    user_id = request.headers.get("X-MS-CLIENT-PRINCIPAL-ID")
    if not user_id:
        return None
    return {
        "id": user_id,
        "name": request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", "Usuario"),
    }


def calculate_budget(usuarios, precio):
    cantidad = int(usuarios)
    importe = Decimal(precio)

    if not 1 <= cantidad <= 1000000:
        raise ValueError
    if not importe.is_finite() or not 0 <= importe <= 1000000:
        raise ValueError
    if importe != importe.quantize(Decimal("0.01")):
        raise ValueError

    total = cantidad * importe
    return cantidad, importe, total, total * 12


def login_redirect(destination):
    return redirect(
        f"/.auth/login/aad?post_login_redirect_uri={destination}"
    )


@app.route("/", methods=["GET", "POST"])
def inicio():
    usuarios = request.form.get("usuarios", "5")
    precio = request.form.get("precio", "10.00")
    mensual = None
    anual = None
    error = None
    user = authenticated_user()

    if request.method == "POST":
        try:
            _, _, total, total_anual = calculate_budget(usuarios, precio)
            mensual = f"{total:.2f}"
            anual = f"{total_anual:.2f}"

        except (ValueError, InvalidOperation):
            error = (
                "Introduce entre 1 y 1.000.000 de usuarios y un precio "
                "entre 0 y 1.000.000 €, con un máximo de dos decimales."
            )

    return render_template_string(
        PAGINA,
        usuarios=usuarios,
        precio=precio,
        mensual=mensual,
        anual=anual,
        error=error,
        autenticado=user is not None,
    )


@app.route("/privado")
def seccion_privada():
    user = authenticated_user()
    if user is None:
        return login_redirect("/privado")

    error = None
    presupuestos = []
    try:
        # PartitionKey filtering means the app only loads this user's records.
        entities = get_budget_table().query_entities(
            query_filter="PartitionKey eq @owner",
            parameters={"owner": user["id"]},
        )
        for entity in entities:
            presupuestos.append({
                "row_key": entity["RowKey"],
                "usuarios": entity["Users"],
                "precio": entity["UnitPrice"],
                "mensual": entity["MonthlyTotal"],
                "anual": entity["AnnualTotal"],
                "created_at": entity["CreatedAt"],
            })
        presupuestos.sort(key=lambda item: item["created_at"], reverse=True)
    except Exception:
        app.logger.exception("No se pudo consultar el historial de presupuestos.")
        error = "No se pudo cargar el historial. Revisa la configuración de Azure Table Storage."

    return render_template_string(
        PAGINA_PRIVADA,
        nombre=user["name"],
        presupuestos=presupuestos,
        error=error,
    )


@app.route("/guardar", methods=["POST"])
def guardar_presupuesto():
    user = authenticated_user()
    if user is None:
        return login_redirect("/")

    try:
        cantidad, importe, mensual, anual = calculate_budget(
            request.form.get("usuarios", ""),
            request.form.get("precio", ""),
        )
        now = datetime.now(timezone.utc)
        row_key = now.strftime("%Y%m%d%H%M%S%f") + "_" + uuid4().hex
        get_budget_table().create_entity({
            "PartitionKey": user["id"],
            "RowKey": row_key,
            "Users": cantidad,
            "UnitPrice": f"{importe:.2f}",
            "MonthlyTotal": f"{mensual:.2f}",
            "AnnualTotal": f"{anual:.2f}",
            "CreatedAt": now.isoformat(timespec="seconds"),
        })
    except (ValueError, InvalidOperation):
        return "Datos del presupuesto no válidos.", 400
    except Exception:
        app.logger.exception("No se pudo guardar el presupuesto.")
        return "No se pudo guardar. Revisa la configuración de Azure Table Storage.", 503

    return redirect("/privado")


@app.route("/eliminar/<row_key>", methods=["POST"])
def eliminar_presupuesto(row_key):
    user = authenticated_user()
    if user is None:
        return login_redirect("/privado")

    try:
        # Delete is constrained to the signed-in user's partition.
        get_budget_table().delete_entity(partition_key=user["id"], row_key=row_key)
    except Exception:
        app.logger.exception("No se pudo eliminar el presupuesto.")
        return "No se pudo eliminar el presupuesto.", 503

    return redirect("/privado")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)

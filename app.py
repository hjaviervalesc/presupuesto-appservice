from decimal import Decimal, InvalidOperation

from flask import Flask, redirect, render_template_string, request

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
    {% endif %}

    <p><a href="/privado">Abrir sección privada (inicio de sesión Microsoft)</a></p>
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
    <title>Sección privada</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #f1f5f9; color: #172033; margin: 0; padding: 48px 20px; }
        main { max-width: 520px; margin: auto; padding: 32px; background: white; border-radius: 16px; box-shadow: 0 8px 30px #17203312; }
    </style>
</head>
<body>
<main>
    <h1>Sección privada</h1>
    <p>Has iniciado sesión con Microsoft Entra ID.</p>
    <p>Usuario autenticado: <strong>{{ nombre }}</strong></p>
    <p><a href="/">Volver a la calculadora</a></p>
    <p><a href="/.auth/logout?post_logout_redirect_uri=/">Cerrar sesión</a></p>
</main>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def inicio():
    usuarios = request.form.get("usuarios", "5")
    precio = request.form.get("precio", "10.00")
    mensual = None
    anual = None
    error = None

    if request.method == "POST":
        try:
            cantidad = int(usuarios)
            importe = Decimal(precio)

            if not 1 <= cantidad <= 1000000:
                raise ValueError

            if not importe.is_finite() or not 0 <= importe <= 1000000:
                raise ValueError

            if importe != importe.quantize(Decimal("0.01")):
                raise ValueError

            total = cantidad * importe
            mensual = f"{total:.2f}"
            anual = f"{total * 12:.2f}"

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
    )


@app.route("/privado")
def seccion_privada():
    # Este encabezado lo inyecta App Service Authentication (Easy Auth)
    # después de validar la sesión de Microsoft Entra ID.
    usuario_id = request.headers.get("X-MS-CLIENT-PRINCIPAL-ID")

    if not usuario_id:
        # La calculadora sigue siendo pública; solo esta ruta pide iniciar sesión.
        return redirect(
            "/.auth/login/aad?post_login_redirect_uri=/privado"
        )

    nombre = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", "Usuario")
    return render_template_string(PAGINA_PRIVADA, nombre=nombre)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)

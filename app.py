import tempfile
import os
from flask import Flask, request, redirect, send_file, jsonify
from skimage import io
import base64
import glob
import numpy as np

app = Flask(__name__)

# === Config común (local + PythonAnywhere) ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIGURAS = ["estrella", "corazon", "rombo"]


def ensure_dirs():
    """Crear las carpetas de figuras si no existen."""
    for f in FIGURAS:
        dir_path = os.path.join(BASE_DIR, f)
        if not os.path.exists(dir_path):
            os.mkdir(dir_path)


# Crear las carpetas al importar el módulo
ensure_dirs()

main_html = """
<html>
<head>
<title>Figuras para PDI</title>
</head>
<script>
  var mousePressed = false;
  var lastX, lastY;
  var ctx;
  var figuraActual = "estrella"; // valor por defecto

  // Leer parámetro de la URL (?figura=rombo, por ejemplo)
  function getQueryParam(name) {
      name = name.replace(/[\\[\\]]/g, "\\\\$&");
      var regex = new RegExp("[?&]" + name + "(=([^&#]*)|&|#|$)");
      var results = regex.exec(window.location.href);
      if (!results || !results[2]) return null;
      return decodeURIComponent(results[2].replace(/\\+/g, " "));
  }

  function InitThis() {
      ctx = document.getElementById('myCanvas').getContext("2d");

      // Referencia al combo de selección
      var selector = document.getElementById('figura_select');

      // Si en la URL viene ?figura=..., la usamos para mantener la última figura
      var figuraURL = getQueryParam("figura");
      if (figuraURL) {
          selector.value = figuraURL;  // estrella / corazon / rombo
      }

      // Valor inicial (lo que esté seleccionado en el combo)
      figuraActual = selector.value;
      actualizarMensajeYHidden();

      // Cuando el usuario cambie de figura en el combo
      selector.onchange = function() {
          figuraActual = this.value;
          actualizarMensajeYHidden();
      };

      // Eventos del mouse para dibujar
      $('#myCanvas').mousedown(function (e) {
          mousePressed = true;
          Draw(e.pageX - $(this).offset().left, e.pageY - $(this).offset().top, false);
      });

      $('#myCanvas').mousemove(function (e) {
          if (mousePressed) {
              Draw(e.pageX - $(this).offset().left, e.pageY - $(this).offset().top, true);
          }
      });

      $('#myCanvas').mouseup(function (e) {
          mousePressed = false;
      });
      $('#myCanvas').mouseleave(function (e) {
          mousePressed = false;
      });

      // Cargar contadores al iniciar
      actualizarContadores();
  }

  function actualizarMensajeYHidden() {
      document.getElementById('mensaje').innerHTML  = 'Dibujando la figura: ' + figuraActual;
      document.getElementById('numero').value = figuraActual;
  }

  function Draw(x, y, isDown) {
      if (isDown) {
          ctx.beginPath();
          ctx.strokeStyle = 'black';
          ctx.lineWidth = 3; // pincel delgado
          ctx.lineJoin = "round";
          ctx.moveTo(lastX, lastY);
          ctx.lineTo(x, y);
          ctx.closePath();
          ctx.stroke();
      }
      lastX = x; lastY = y;
  }

  function clearArea() {
      // Use the identity matrix while clearing the canvas
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
  }

  //https://www.askingbox.com/tutorial/send-html5-canvas-as-image-to-server
  function prepareImg() {
     var canvas = document.getElementById('myCanvas');
     document.getElementById('myImage').value = canvas.toDataURL();
  }

  // Pide al backend los contadores por figura y los muestra
  function actualizarContadores() {
      $.getJSON('/counts', function(data) {
          document.getElementById('count_estrella').innerHTML = data.estrella || 0;
          document.getElementById('count_corazon').innerHTML = data.corazon || 0;
          document.getElementById('count_rombo').innerHTML = data.rombo || 0;
      });
  }

</script>
<body onload="InitThis();">
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/1.7.1/jquery.min.js" type="text/javascript"></script>
    <script type="text/javascript" ></script>
    <div align="left">
      <img src="https://upload.wikimedia.org/wikipedia/commons/f/fc/UPC_logo_transparente.png" width="150"/>
    </div>
    <div align="center">
        <h1 id="mensaje">Dibujando...</h1>

        <!-- Selector manual de figura -->
        <label for="figura_select"><b>Elige la figura:</b></label>
        <select id="figura_select">
          <option value="estrella">Estrella</option>
          <option value="corazon">Corazón</option>
          <option value="rombo">Rombo</option>
        </select>

        <br/><br/>

        <!-- Contadores de ejemplos por figura -->
        <div id="contadores" style="margin-bottom: 10px;">
          <b>Contador de dibujos guardados:</b><br/>
          Estrella: <span id="count_estrella">0</span><br/>
          Corazón: <span id="count_corazon">0</span><br/>
          Rombo: <span id="count_rombo">0</span><br/>
        </div>

        <canvas id="myCanvas" width="200" height="200" style="border:2px solid black"></canvas>
        <br/><br/>

        <!-- Botón borrar dibujo -->
        <button onclick="javascript:clearArea();return false;">Borrar</button>

        <br/><br/>

        <!-- Formulario para enviar el dibujo -->
        <form method="post" action="upload" onsubmit="javascript:prepareImg();" enctype="multipart/form-data">
          <input id="numero" name="numero" type="hidden" value="">
          <input id="myImage" name="myImage" type="hidden" value="">
          <input id="bt_upload" type="submit" value="Enviar">
        </form>

        <br/>

        <!-- Botón para procesar las imágenes y generar X e y -->
        <form method="get" action="/prepare">
          <button type="submit">Procesar imágenes (generar X e y)</button>
        </form>

        <br/>

        <!-- Enlaces para descargar los .npy -->
        <div>
          <a href="/X.npy">Descargar X.npy (vectores)</a><br/>
          <a href="/y.npy">Descargar y.npy (etiquetas)</a>
        </div>
    </div>
</body>
</html>
"""


@app.route("/")
def main():
    return main_html


@app.route('/upload', methods=['POST'])
def upload():
    try:
        # obtenemos la imagen desde el formulario (base64)
        img_data = request.form.get('myImage').replace("data:image/png;base64,", "")
        figura = request.form.get('numero')  # estrella / corazon / rombo
        print("Figura recibida:", figura)

        # carpeta absoluta para esa figura
        dir_path = os.path.join(BASE_DIR, figura)
        if not os.path.exists(dir_path):
            os.mkdir(dir_path)

        with tempfile.NamedTemporaryFile(
            delete=False,
            mode="w+b",
            suffix='.png',
            dir=dir_path
        ) as fh:
            fh.write(base64.b64decode(img_data))

        print("Image uploaded")
    except Exception as err:
        print("Error occurred")
        print(err)

    # Redirigimos a / pero manteniendo la figura en la URL
    return redirect(f"/?figura={figura}", code=302)


def crear_dataset():
    """
    Lee todas las imágenes de estrella/corazon/rombo, las convierte en vectores
    y guarda X.npy (vectores) e y.npy (etiquetas).
    """
    images = []
    labels = []

    for figura in FIGURAS:
        pattern = os.path.join(BASE_DIR, figura, '*.png')
        filelist = glob.glob(pattern)
        if len(filelist) == 0:
            continue  # por si todavía no hay imágenes en esta carpeta

        # Leer todas las imágenes de esa figura
        imgs = io.concatenate_images(io.imread_collection(filelist))
        # Tomamos el canal alfa como en tu código original
        imgs = imgs[:, :, :, 3]       # shape: (n_imagenes, alto, ancho)

        n = imgs.shape[0]

        # Convertir cada imagen en un vector 1D
        imgs_vec = imgs.reshape(n, -1)   # shape: (n_imagenes, alto*ancho)

        images.append(imgs_vec)
        labels.append(np.array([figura] * n))

    if not images:
        return None, None

    X = np.vstack(images)          # shape: (total_imágenes, alto*ancho)
    y = np.concatenate(labels)     # shape: (total_imágenes,)

    # Guardamos en disco
    np.save(os.path.join(BASE_DIR, 'X.npy'), X)
    np.save(os.path.join(BASE_DIR, 'y.npy'), y)

    return X, y


@app.route('/prepare', methods=['GET'])
def prepare_dataset():
    X, y = crear_dataset()
    if X is None:
        return "No hay imágenes aún"

    return f"Dataset preparado. X.shape = {X.shape}, y.shape = {y.shape}"


@app.route('/X.npy', methods=['GET'])
def download_X():
    return send_file(os.path.join(BASE_DIR, 'X.npy'), as_attachment=True)


@app.route('/y.npy', methods=['GET'])
def download_y():
    return send_file(os.path.join(BASE_DIR, 'y.npy'), as_attachment=True)


# Nueva ruta: devuelve los contadores por figura en JSON
@app.route('/counts', methods=['GET'])
def counts():
    data = {}
    for f in FIGURAS:
        pattern = os.path.join(BASE_DIR, f, '*.png')
        data[f] = len(glob.glob(pattern))
    return jsonify(data)


if __name__ == "__main__":
    # Para correrlo en tu PC local
    app.run(host="0.0.0.0", port=5000)

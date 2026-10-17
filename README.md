# Marcador Fútbol Chile

Resultados en vivo de fútbol, con el canal donde se ve cada partido en Chile.

**Ligas incluidas:** Chile, España, Inglaterra, Alemania y Argentina, con sus copas y segundas divisiones.

## Cómo funciona

- Es una sola página (`index.html`), sin servidor ni base de datos.
- El navegador consulta dos fuentes, ESPN y FotMob, y las contrasta. Si no coinciden, muestra el dato más actualizado.
- El botón **Actualizar** fuerza una consulta inmediata. Además, la página se actualiza sola:
  - cada **30 segundos** cuando hay un partido en vivo o por empezar;
  - cada **5 minutos** el resto del tiempo.
- Si la pestaña queda en segundo plano, deja de consultar. Al volver a ella se actualiza de inmediato.
- Las horas se muestran en hora de Chile (`America/Santiago`).

- Al tocar un partido en vivo o terminado se despliegan los goles (minuto, autor, penales y autogoles), y las expulsiones. Los partidos sin goles no se despliegan.

## Publicarla con GitHub Pages

1. En el repositorio, abre **Settings → Pages**.
2. En **Source** elige **Deploy from a branch**.
3. Selecciona la rama `main` y la carpeta `/ (root)`, y presiona **Save**.
4. En uno o dos minutos la página queda en `https://<tu-usuario>.github.io/marcador-cl/`.

## Cambiar torneos o canales

Edita la lista `TORNEOS` al comienzo del `<script>` en `index.html`. Cada torneo tiene tres datos:

- `slug`: el código del torneo en ESPN (por ejemplo, `chi.1` o `eng.1`).
- `nombre`: cómo se muestra en la página.
- `tv`: el canal en Chile.

Los canales no vienen de la API. Revísalos al inicio de cada temporada, porque los derechos de transmisión cambian.

## Limitaciones

La API de ESPN no es oficial y puede cambiar sin aviso. Si un torneo deja de responder, la página lo omite y muestra el resto.

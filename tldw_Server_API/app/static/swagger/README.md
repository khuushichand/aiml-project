Place local Swagger UI assets here to avoid CSP/CDN issues with /docs.

Required files (matching the same version):
- swagger-ui-bundle.js
- swagger-ui-standalone-preset.js
- swagger-ui.css

Optional (favicons, fonts, etc.)
- favicon-16x16.png
- favicon-32x32.png

Paths expected by the server:
- JS bundle:          /static/swagger/swagger-ui-bundle.js
- Standalone preset:  /static/swagger/swagger-ui-standalone-preset.js
- CSS:                /static/swagger/swagger-ui.css

How to populate (pick one):
1) If you have npm:
   npm i swagger-ui-dist@latest
   cp node_modules/swagger-ui-dist/{swagger-ui-bundle.js,swagger-ui-standalone-preset.js,swagger-ui.css,favicon-16x16.png,favicon-32x32.png} tldw_Server_API/app/static/swagger/

2) With Python + network allowed:
   pip install swagger-ui-dist
   python - << 'PY'
import pkgutil, shutil, pathlib, swagger_ui_dist
src = pathlib.Path(swagger_ui_dist.__file__).parent
dst = pathlib.Path('tldw_Server_API/app/static/swagger')
dst.mkdir(parents=True, exist_ok=True)
for name in ['swagger-ui-bundle.js','swagger-ui-standalone-preset.js','swagger-ui.css','favicon-16x16.png','favicon-32x32.png']:
    shutil.copy2(src / name, dst / name)
print('Copied Swagger UI assets to', dst)
PY

3) Download directly (if allowed):
   curl -o tldw_Server_API/app/static/swagger/swagger-ui-bundle.js         https://cdn.jsdelivr.net/npm/swagger-ui-dist@latest/swagger-ui-bundle.js
   curl -o tldw_Server_API/app/static/swagger/swagger-ui-standalone-preset.js https://cdn.jsdelivr.net/npm/swagger-ui-dist@latest/swagger-ui-standalone-preset.js
   curl -o tldw_Server_API/app/static/swagger/swagger-ui.css                 https://cdn.jsdelivr.net/npm/swagger-ui-dist@latest/swagger-ui.css

Once the files are in place, restart the server. The app auto-detects local assets and serves them at /docs.

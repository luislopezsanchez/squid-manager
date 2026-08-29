# Idiomas — SquidManager

El panel está disponible en **español, inglés y portugués**. Se elige desde el
selector que hay al final del menú lateral, junto a «Cambiar contraseña».

Hay tres superficies de texto distintas, y conviene no confundirlas porque se
traducen de formas diferentes:

| Qué | Quién lo ve | Cómo se traduce |
|---|---|---|
| El panel | El administrador | Diccionarios del frontend |
| Los mensajes de la API | El administrador, al fallar algo | Diccionario del backend, por `Accept-Language` |
| Las páginas de error del proxy | **Los usuarios finales** que navegan | Las trae Squid, se elige con un ajuste |

---

## La decisión de fondo: la clave es el texto en español

En los dos diccionarios, la clave de cada texto **es el propio texto en
español**, no un identificador inventado (`paginas.acl.titulo`). Es el enfoque
de gettext, y resuelve dos problemas concretos de traducir una aplicación que ya
existía:

- **No hay que bautizar cientos de cadenas** ni mantener esa nomenclatura al día.
- **Lo que falte por traducir sale en español**, que es un idioma real, en lugar
  de aparecer como un identificador interno. Una traducción incompleta se ve
  imperfecta, no rota — y por eso se puede publicar sin tenerlo todo hecho.

El coste es el esperable: si alguien cambia un texto en español, esa cadena deja
de tener traducción y vuelve a salir en español hasta que se actualice la clave.
Es un fallo visible y sin consecuencias, no una pantalla en blanco.

---

## El panel

```
frontend/src/i18n/
├── index.ts     # la función traducir(), el idioma activo y el selector
├── en.json      # español -> inglés
└── pt.json      # español -> portugués
```

No hay `es.json`: el español son las claves.

`traducir` es **una función de módulo, no un hook de React**. Es deliberado:
buena parte del texto de la interfaz vive en constantes que se evalúan antes de
que exista ningún componente —etiquetas de los tipos de ACL, clases de delay
pool, columnas de tablas—. Con un hook habría que mover todas esas constantes
dentro de los componentes.

La contrapartida es que **cambiar de idioma recarga la página**. React no tiene
forma de saber que hay que volver a pintar, y los textos ya evaluados en
constantes no se recalcularían nunca. En un panel de administración el idioma se
elige una vez, así que la recarga no molesta.

El idioma elegido se guarda en `localStorage`. Si no hay ninguno guardado se usa
el del navegador, y si tampoco encaja, español.

### Añadir un idioma

1. Crea `frontend/src/i18n/<código>.json` con las mismas claves que `en.json`.
2. Impórtalo en `index.ts` y añádelo a `DICCIONARIOS` y a `IDIOMAS`.
3. Añade el código a la unión de tipos `Idioma`.

Lo que no traduzcas saldrá en español, así que se puede empezar por lo más
visible e ir completando.

### Qué no se traduce, y por qué

44 de las 453 cadenas del panel se dejan tal cual a propósito: comandos
(`sudo update-ca-certificates`), nombres de directivas de Squid (`dstdomain`,
`url_regex`, `http_access`), ejemplos de configuración y direcciones de ejemplo.
Son iguales en los tres idiomas y traducirlas sería un error.

---

## Los mensajes de la API

Traducir solo el panel deja una aplicación que está en inglés **hasta que algo
falla**, y entonces contesta en español — justo en el momento de más fricción
para quien la usa. Por eso el backend también traduce.

- Diccionario: `backend/app/i18n.py`.
- Se aplica en **un solo manejador de excepciones** (`app/main.py`), no en los
  60 sitios donde se lanzan los mensajes.
- El idioma sale de la cabecera **`Accept-Language`** de cada petición.

El panel manda ahí **el idioma que ha elegido el administrador**, que no tiene
por qué coincidir con el del navegador. Un navegador cualquiera manda su lista
completa (`en-US,en;q=0.9,es;q=0.8`) y se usa la primera coincidencia; si no hay
ninguna, español.

```bash
curl -H "Accept-Language: en" ...   # {"detail":"Rule not found"}
curl -H "Accept-Language: pt" ...   # {"detail":"Regra não encontrada"}
curl ...                            # {"detail":"Regla no encontrada"}
```

Los mensajes puramente internos —fallos de Docker Compose, sincronización del
`.env`— no están traducidos a propósito: no los ve un administrador en su día a
día, los ve quien lee un log, y ahí el español del proyecto es lo útil.

---

## Las páginas de error del proxy

Son las que ve **el usuario final** cuando el proxy le deniega el acceso o algo
falla, y no tienen nada que ver con el idioma del panel: las genera Squid.

Se controlan con el ajuste **«Idioma de las páginas de error»**
(`error_language`), en Configuración → General. Por defecto `es`.

Squid resuelve además el idioma por el `Accept-Language` del navegador de cada
usuario, así que en una empresa con gente de varios países cada uno puede ver el
aviso en el suyo sin configurar nada.

- **Modo nativo:** el paquete `squid-langpack` trae **203 juegos de páginas**,
  incluidos `es`, `es-es`, `es-uy`, `en`, `en-us`, `pt`, `pt-br` y `pt-pt`. Lo
  instala `install-nativo.sh`.
- **Modo Docker:** las traducciones vienen en el código fuente de Squid y se
  copian al construir la imagen, que además crea enlaces para las variantes
  regionales del español (`es-es` → `es`), sin los cuales un Firefox en español
  de España veía un error genérico en lugar de la página de acceso denegado.

---

## Qué no está traducido

**La documentación.** Son más de 4.000 líneas que se desincronizarían a la
primera versión, y mantenerlas en tres idiomas cuesta más que traducir el
producto entero. Está en español, salvo lo que se decida traducir puntualmente
del README.

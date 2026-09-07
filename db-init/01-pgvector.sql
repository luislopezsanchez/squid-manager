-- La imagen pgvector/pgvector trae la extensión compilada, pero no la deja
-- creada sola: hace falta este CREATE EXTENSION. El propio mecanismo de
-- postgres monta todo lo que hay en /docker-entrypoint-initdb.d/ (via
-- docker-compose.yml) y lo corre como superusuario, una sola vez, al
-- inicializar un volumen de datos vacío. En un volumen que ya existía de
-- antes de esta versión, este script no vuelve a correr solo -ver
-- docs/actualizacion.md para el paso manual equivalente-.
CREATE EXTENSION IF NOT EXISTS vector;

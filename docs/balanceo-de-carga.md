# Varios Squid detrás de un balanceador — SquidManager

Squid no tiene un modo nativo de clustering activo-activo con estado
compartido, y SquidManager tampoco lo puede añadir por su cuenta: no existe
ninguna directiva de `squid.conf` para eso. Lo que sí es viable — y es el
patrón estándar de la industria para escalar Squid — es poner varias
instancias independientes detrás de un balanceador externo. Esta guía cubre
esa topología, sus límites reales, y qué parte SquidManager ya resuelve hoy.

---

## La topología

```
                     ┌─────────────────┐
                     │  Balanceador     │   (HAProxy, keepalived+VRRP,
   Clientes ───────► │  (capa 4, TCP)   │    o el balanceador de tu nube)
                     └────────┬─────────┘
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
        ┌───────────┐ ┌───────────┐ ┌───────────┐
        │ Nodo 1     │ │ Nodo 2     │ │ Nodo 3     │
        │ SquidManager│ │SquidManager│ │SquidManager│
        │ + Squid    │ │ + Squid    │ │ + Squid    │
        │ (propios)  │ │ (propios)  │ │ (propios)  │
        └───────────┘ └───────────┘ └───────────┘
```

Cada nodo es una instalación completa e independiente de SquidManager (ver
[production.md](production.md) — "para más de un nodo, se despliega una
instancia de SquidManager por nodo"), con su propia base de datos, su propio
Squid y su propia caché. El balanceador solo reparte el tráfico de los
clientes hacia el puerto del proxy (3128) de cada nodo — **el panel web de
administración de cada nodo sigue siendo independiente**, no hay un panel
único que controle los tres Squid (para eso, ver la función de "monitoreo
centralizado" en [project-log.md](project-log.md), aún no implementada, que
sí permitirá *ver* los tres desde un solo lugar, pero no fusiona su
configuración en una sola).

---

## Afinidad de sesión: el punto que rompe instalaciones si se ignora

Con **Basic Auth**, cualquier nodo puede validar cualquier request de forma
independiente — el balanceador puede repartir round-robin sin problema,
siempre que los tres nodos tengan la misma lista de usuarios.

Con **Kerberos/Negotiate o NTLM** (que SquidManager soporta — ver
[kerberos.md](kerberos.md)), la negociación es **con estado**, atada a la
conexión TCP contra un nodo concreto. Un balanceador que reparte
round-robin puro corta esa negociación a la mitad. Es necesario configurar
**afinidad por IP de cliente** (`balance source` en HAProxy, o el
equivalente en tu balanceador) — no es opcional con estos esquemas.

---

## Mantener la configuración igual entre nodos: lo que ya existe hoy

No hace falta esperar a una función nueva para esto — **Backup y migración**
(ver [backup-restore.md](backup-restore.md)) ya exporta ACLs, reglas de
acceso y delay pools a un JSON descargable e importable. El flujo manual
hoy mismo:

1. Configurar ACLs/reglas/delay pools en el **Nodo 1** como corresponde.
2. **Backup y migración → Descargar backup (JSON)** en el Nodo 1.
3. **Restaurar backup** con ese mismo archivo en el Nodo 2 y el Nodo 3.

Con matices a tener en cuenta, ya documentados en
[backup-restore.md](backup-restore.md#notas-importantes):

- **Reglas de acceso y delay pools se reemplazan por completo** al
  restaurar — así que sí quedan idénticas a las del nodo origen.
- **Los usuarios del proxy se restauran deshabilitados y sin contraseña**:
  esto sirve para igualar ACLs/reglas/grupos entre nodos, pero **no** es un
  mecanismo turnkey para tener los mismos usuarios navegando en los tres —
  cada uno necesitaría que se le resetee la contraseña en cada nodo. Si la
  autenticación es contra LDAP/AD, este problema no existe: cada nodo
  sincroniza contra el mismo directorio de forma independiente.
- Es un proceso **manual**, repetido nodo por nodo — no hay (todavía) un
  botón de "aplicar a todos los nodos". Automatizar esto es la extensión
  natural de esta guía si se retoma el tema, pero no es indispensable para
  arrancar.

---

## Ejemplo de balanceador (HAProxy)

Balanceo por capa 4 (TCP), con afinidad por IP de origen — imprescindible si
hay Kerberos/NTLM activado en cualquier nodo:

```haproxy
frontend proxy_in
    bind *:3128
    mode tcp
    default_backend squid_nodes

backend squid_nodes
    mode tcp
    balance source
    option tcp-check
    server nodo1 10.0.0.11:3128 check
    server nodo2 10.0.0.12:3128 check
    server nodo3 10.0.0.13:3128 check
```

`option tcp-check` saca del pool a un nodo cuyo Squid dejó de responder,
sin necesitar nada especial de SquidManager para eso.

Para que el propio balanceador no sea un punto único de falla, sumale
`keepalived` con VRRP (una IP virtual flotando entre dos balanceadores) —
queda fuera del alcance de esta guía porque es infraestructura genérica de
HAProxy, no algo específico de SquidManager.

---

## Qué NO resuelve esta topología

- **No hay caché compartida.** Cada nodo cachea lo que pasa por él; un
  mismo objeto puede descargarse una vez por nodo. Para Squid esto es
  normal y esperado, no un bug.
- **No hay una sola fuente de verdad de configuración.** Cada base de datos
  es independiente; el JSON de backup/restore sincroniza en un momento
  dado, no continuamente.
- **No es alta disponibilidad automática de la configuración**: si cambiás
  una regla en el Nodo 1, no se propaga sola a los demás.

Si con el tiempo hace falta resolver el último punto de forma automática,
está anotado como posible mejora futura en
[project-log.md](project-log.md#evaluado-alcance-reducido-clustering-de-squid-para-balanceo-de-carga).

// Contenido del artículo "Proxy padre" de la biblioteca de Documentación.
// Ver docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_PROXY_PADRE: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Hace que este Squid salga a Internet a través de **otro** proxy, en vez de directo. Necesario en redes donde el cortafuegos no permite la salida directa y todo el tráfico tiene que pasar por un proxy corporativo ya existente.

## Credenciales: dos formas de presentarlas al padre

- **Fijas**: SquidManager guarda un usuario y contraseña propios y los presenta al padre en cada conexión, sin importar quién sea el cliente real. Squid solo sabe hacer esto con autenticación **básica** -si el proxy padre exige NTLM, Digest o Kerberos, esta opción no sirve.
- **Passthru**: reenvía tal cual las credenciales que ya trae el cliente. Es la única forma de llegar a un padre que exige Digest, NTLM o Negotiate. A cambio, **no se puede combinar** con que este mismo SquidManager autentique a sus propios clientes (HTTP solo permite una credencial por petición) -si hay usuarios locales, LDAP o Kerberos activos, guardar 'passthru' se rechaza hasta desactivarlos.

El botón de prueba dice cuál de las dos hace falta si no se sabe de antemano.

## Salida directa vs. nunca directa

Con **"No intentar nunca la salida directa"** activado (recomendado cuando hay proxy corporativo), si el padre no responde, la conexión falla de inmediato en vez de intentar salir directo primero -evita una espera inútil cuando ya se sabe que el cortafuegos bloquea esa salida. Desactivarlo solo tiene sentido si la red realmente permite las dos vías.

## Dominios de salida directa

Una lista de dominios que se excluyen del padre y salen directo -típicamente, servicios internos que el proxy padre no necesita ver, o que no son alcanzables desde ahí.

## Certificado del padre

Si el proxy padre también intercepta HTTPS con su propio certificado, hay que cargar ese certificado (formato PEM) para que este Squid confíe en él -sin esto, el tráfico HTTPS a través del padre fallaría por certificado no confiable.
`.trim(),
  en: `
## What this is for

Makes this Squid reach the Internet through **another** proxy, instead of directly. Needed on networks where the firewall doesn't allow direct outbound access and all traffic has to go through an existing corporate proxy.

## Credentials: two ways to present them to the parent

- **Fixed**: SquidManager stores its own username and password and presents them to the parent on every connection, regardless of who the real client is. Squid only knows how to do this with **basic** authentication -if the parent proxy requires NTLM, Digest or Kerberos, this option won't work.
- **Passthru**: forwards the client's own credentials as-is. It's the only way to reach a parent that requires Digest, NTLM or Negotiate. In exchange, it **can't be combined** with this same SquidManager authenticating its own clients (HTTP only allows one credential per request) -if local users, LDAP or Kerberos are active, saving 'passthru' is rejected until they're turned off.

The test button tells you which of the two is needed if you don't know beforehand.

## Direct exit vs. never direct

With **"Never attempt direct exit"** enabled (recommended when there's a corporate proxy), if the parent doesn't respond, the connection fails immediately instead of trying to go out directly first -avoids a pointless wait when it's already known the firewall blocks that path. Turning it off only makes sense if the network genuinely allows both routes.

## Direct-exit domains

A list of domains excluded from the parent that go out directly -typically internal services the parent proxy doesn't need to see, or that aren't reachable from there.

## Parent's certificate

If the parent proxy also intercepts HTTPS with its own certificate, that certificate (PEM format) needs to be uploaded so this Squid trusts it -without it, HTTPS traffic through the parent would fail with an untrusted certificate error.
`.trim(),
  pt: `
## Para que serve

Faz este Squid sair para a Internet através de **outro** proxy, em vez de diretamente. Necessário em redes onde o firewall não permite saída direta e todo o tráfego precisa passar por um proxy corporativo já existente.

## Credenciais: duas formas de apresentá-las ao pai

- **Fixas**: o SquidManager guarda um usuário e senha próprios e os apresenta ao pai em cada conexão, não importa quem seja o cliente real. O Squid só sabe fazer isso com autenticação **básica** -se o proxy pai exige NTLM, Digest ou Kerberos, essa opção não serve.
- **Passthru**: reenvia tal como estão as credenciais que o cliente já traz. É a única forma de chegar a um pai que exige Digest, NTLM ou Negotiate. Em troca, **não pode ser combinado** com este mesmo SquidManager autenticando seus próprios clientes (HTTP só permite uma credencial por requisição) -se há usuários locais, LDAP ou Kerberos ativos, salvar 'passthru' é rejeitado até que sejam desativados.

O botão de teste diz qual das duas é necessária se não se souber de antemão.

## Saída direta vs. nunca direta

Com **"Nunca tentar a saída direta"** ativado (recomendado quando há proxy corporativo), se o pai não responder, a conexão falha imediatamente em vez de tentar sair direto primeiro -evita uma espera inútil quando já se sabe que o firewall bloqueia essa saída. Desativar só faz sentido se a rede realmente permite as duas vias.

## Domínios de saída direta

Uma lista de domínios excluídos do pai que saem direto -tipicamente, serviços internos que o proxy pai não precisa ver, ou que não são alcançáveis a partir de lá.

## Certificado do pai

Se o proxy pai também intercepta HTTPS com seu próprio certificado, esse certificado (formato PEM) precisa ser carregado para que este Squid confie nele -sem isso, o tráfego HTTPS através do pai falharia por certificado não confiável.
`.trim(),
}

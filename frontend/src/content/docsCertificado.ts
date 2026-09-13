// Contenido del artículo "Certificado" de la biblioteca de Documentación.
// Ver docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_CERTIFICADO: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Con SSL Bump activado, Squid intercepta HTTPS presentando un certificado propio generado al vuelo, firmado por una autoridad certificadora (CA) que el propio SquidManager crea. Para que el navegador de cada usuario no muestre una advertencia de "conexión no segura", esa CA tiene que instalarse como confiable en cada equipo cliente **una sola vez**.

## Descargar el certificado

El botón descarga el certificado público de la CA (\`.crt\`) -no la clave privada, esa nunca sale del servidor. Es seguro distribuirlo: es lo mismo que hace cualquier autoridad certificadora pública, solo que esta es propia de la organización.

## Instalarlo, según el caso

- **Active Directory (GPO)**: para distribuirlo automáticamente a todos los equipos del dominio, sin tocarlos uno por uno.
- **Perfil de configuración (Mac/iOS)**: instalable por doble clic en Mac, o enviado por MDM en iPhone/iPad.
- **Windows manual**: importar a "Entidades de certificación raíz de confianza".
- **Firefox**: Firefox mantiene su propio almacén de certificados, separado del sistema operativo -instalar la CA en Windows/Mac no alcanza para que Firefox confíe en ella, hay que agregarla también ahí (\`about:preferences\` → Certificados).
- **Linux**: agregar al almacén de confianza del sistema.

## Si el certificado no está disponible

La página avisa si todavía no hay una CA generada -pasa la primera vez que se instala SquidManager, antes de la primera aplicación de configuración con SSL Bump activo.
`.trim(),
  en: `
## What this is for

With SSL Bump enabled, Squid intercepts HTTPS by presenting its own certificate generated on the fly, signed by a certificate authority (CA) that SquidManager itself creates. For each user's browser to not show a "connection not secure" warning, that CA needs to be installed as trusted on every client machine **once**.

## Downloading the certificate

The button downloads the CA's public certificate (\`.crt\`) -not the private key, that never leaves the server. It's safe to distribute: it's the same thing any public certificate authority does, just that this one belongs to the organization.

## Installing it, depending on the case

- **Active Directory (GPO)**: to distribute it automatically to every domain machine, without touching them one by one.
- **Configuration profile (Mac/iOS)**: installable by double-clicking on Mac, or pushed via MDM on iPhone/iPad.
- **Manual on Windows**: import into "Trusted Root Certification Authorities".
- **Firefox**: Firefox keeps its own certificate store, separate from the operating system -installing the CA on Windows/Mac isn't enough for Firefox to trust it, it has to be added there too (\`about:preferences\` → Certificates).
- **Linux**: add to the system's trust store.

## If the certificate isn't available

The page warns if a CA hasn't been generated yet -this happens the first time SquidManager is installed, before the first configuration apply with SSL Bump enabled.
`.trim(),
  pt: `
## Para que serve

Com SSL Bump ativado, o Squid intercepta HTTPS apresentando um certificado próprio gerado na hora, assinado por uma autoridade certificadora (CA) que o próprio SquidManager cria. Para que o navegador de cada usuário não mostre um aviso de "conexão não segura", essa CA precisa ser instalada como confiável em cada máquina cliente **uma única vez**.

## Baixar o certificado

O botão baixa o certificado público da CA (\`.crt\`) -não a chave privada, essa nunca sai do servidor. É seguro distribuí-lo: é a mesma coisa que qualquer autoridade certificadora pública faz, só que essa é própria da organização.

## Instalar, conforme o caso

- **Active Directory (GPO)**: para distribuir automaticamente para todas as máquinas do domínio, sem precisar mexer uma por uma.
- **Perfil de configuração (Mac/iOS)**: instalável com duplo clique no Mac, ou enviado por MDM em iPhone/iPad.
- **Windows manual**: importar em "Autoridades de Certificação Raiz Confiáveis".
- **Firefox**: o Firefox mantém seu próprio repositório de certificados, separado do sistema operacional -instalar a CA no Windows/Mac não é suficiente para o Firefox confiar nela, é preciso adicioná-la lá também (\`about:preferences\` → Certificados).
- **Linux**: adicionar ao repositório de confiança do sistema.

## Se o certificado não estiver disponível

A página avisa se ainda não há uma CA gerada -isso acontece na primeira vez que o SquidManager é instalado, antes da primeira aplicação de configuração com SSL Bump ativo.
`.trim(),
}

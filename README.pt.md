# SquidManager

**[Español](README.md) · [English](README.en.md) · Português**

<p align="center">
  <strong>Painel web de gerenciamento para Squid Proxy, com FastAPI, React e SSL Bump</strong><br>
  Implanta-se <strong>com Docker</strong> ou <strong>sem Docker</strong>
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-blue.svg">
  <img alt="Squid" src="https://img.shields.io/badge/Squid-6.12-green">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-teal">
  <img alt="React" src="https://img.shields.io/badge/React-18-blue">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-blue">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Compose-blue">
</p>

> **A versão em espanhol é a fonte de verdade.** Se esta tradução e o
> [README.md](README.md) discordarem, o espanhol é o correto.

> ### 🌍 Idiomas da documentação
>
> | | Español | English | Português |
> |---|---|---|---|
> | **README** | [README.md](README.md) | [README.en.md](README.en.md) | este |
> | **Instalar com Docker** | [ver](docs/installation.md) | [view](docs/installation.en.md) | [ver](docs/installation.pt.md) |
> | **Instalar sem Docker** | [ver](docs/instalacion-nativa.md) | [view](docs/instalacion-nativa.en.md) | [ver](docs/instalacion-nativa.pt.md) |
>
> O resto da documentação está só em espanhol. O **painel e as mensagens da
> API** falam os três idiomas: escolhe-se no seletor da barra superior — veja
> [docs/idiomas.md](docs/idiomas.md).

---

## 📋 Índice

- [Descrição](#-descrição)
- [Recursos](#-recursos)
- [Arquitetura](#-arquitetura)
- [Requisitos](#-requisitos)
- [Instalação](#-instalação)
  - [Modo A — com Docker](#modo-a--com-docker)
  - [Modo B — sem Docker (nativa)](#modo-b--sem-docker-instalação-nativa)
- [Atualizar](#-atualizar)
- [Configuração](#-configuração)
- [Primeiros passos](#-primeiros-passos)
- [SSL Bump (HTTPS)](#-ssl-bump-https)
- [Painel web](#-painel-web)
- [API REST](#-api-rest)
- [Documentação](#-documentação)
- [Solução de problemas](#-solução-de-problemas)
- [Licença](#-licença)

---

## 📖 Descrição

O **SquidManager** é uma plataforma completa de gerenciamento do Squid Proxy.
Permite que administradores de rede configurem e administrem um proxy Squid a
partir de uma interface web amigável, sem precisar editar arquivos de
configuração à mão.

O sistema foi pensado para ser **escalável e modular**: o banco de dados é a
fonte de verdade, o arquivo `squid.conf` é gerado dinamicamente a partir do
painel, e tudo roda em contêineres Docker ou como serviços do sistema.

---

## ✨ Recursos

### Gerenciamento do proxy
- **ACLs visuais** — Crie listas de controle de acesso por domínio, IP, horário, regex, porta, método HTTP e mais (27 tipos suportados)
- **Regras de acesso** — Ordene regras `http_access` com botões de subir/descer
- **Grupos de usuários** — Agrupe usuários locais ou LDAP e aplique políticas de acesso ao grupo inteiro de uma vez
- **Delay Pools** — Controle de largura de banda por usuário com interface visual (sem precisar entender o formato `64000/64000 64000/32000`)
- **Configurações gerais** — Porta, cache, logging, realm, hostname visível: tudo editável pela web

### Autenticação
- **Usuários locais** — Gerenciamento completo de usuários com autenticação básica (htpasswd) e data de expiração opcional
- **LDAP / Active Directory** — Integração com diretório externo, com teste de conexão integrado e sincronização paginada
- **Painel seguro** — Login com JWT, papéis (superadmin / admin / somente leitura) e troca de senha obrigatória no primeiro acesso

### Segurança
- **SSL Bump** — Intercepta e filtra tráfego HTTPS, não apenas HTTP
- **Bloqueio de HTTPS por SNI** — Bloqueia domínios antes de descriptografar (ex.: Facebook ou YouTube por HTTPS)
- **Exclusão de domínios sensíveis** — Bancos, saúde ou aplicativos com *certificate pinning* podem ficar de fora da descriptografia
- **Auditoria completa** — Registro de todas as alterações: quem, o quê, quando
- **Certificado CA** — Geração automática e download pelo painel, com instaladores para Windows, macOS e iOS

### Operação
- **Aplicar alterações a quente** — Valida a configuração no Squid *antes* de gravá-la; recarrega ou reinicia conforme necessário
- **Mudança de porta automática** — Detecta a mudança e recria o contêiner sem perder a configuração se algo falhar
- **Painel** — Tráfego em tempo real, principais usuários e domínios, estado do sistema
- **Backup e migração** — Exporte toda a configuração para JSON (incluindo grupos e usuários LDAP) ou importe um `squid.conf` tradicional
- **Notificações** — Alertas por e-mail ou Telegram quando alterações são aplicadas ou se detecta atividade suspeita

### Implantação e idiomas
- **Dois modos de implantação** — Com Docker (um único comando sobe tudo) ou **sem Docker**, com o Squid, o painel e o PostgreSQL como serviços do sistema. Escolhe-se com `DEPLOY_MODE`; o resto do produto é idêntico — veja [docs/instalacion-nativa.pt.md](docs/instalacion-nativa.pt.md)
- **Sem root** — No modo nativo o painel roda com seu próprio usuário e um sudoers de três comandos, bem menos do que o socket do Docker concede
- **Painel em três idiomas** — Espanhol, inglês e português, selecionável no próprio painel. As mensagens de erro da API também são traduzidas, e as páginas de erro que os usuários do proxy veem seguem o idioma deles — veja [docs/idiomas.md](docs/idiomas.md)

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Network                        │
│                                                          │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐        │
│  │ Frontend  │     │ Backend  │     │ Squid    │        │
│  │ (React)  │────▶│ (FastAPI)│────▶│ Proxy    │        │
│  │ :3000    │     │ :8000    │     │ :3128    │        │
│  └──────────┘     └────┬─────┘     └──────────┘        │
│                        │                                 │
│                   ┌────▼─────┐                          │
│                   │PostgreSQL│                          │
│                   │  :5432   │                          │
│                   └──────────┘                          │
└─────────────────────────────────────────────────────────┘

Fluxo de configuração:
  Admin → Painel web → API REST → PostgreSQL → Jinja2 → squid.conf → Squid
```

**Princípio central:** o banco de dados é a fonte de verdade. O `squid.conf` é
gerado dinamicamente com Jinja2 a partir dos dados no PostgreSQL. Ao clicar em
"Aplicar alterações", o backend gera o arquivo, **valida executando
`squid -k parse` onde o Squid realmente está**, e só grava e recarrega se for
válido.

> A porta 8000 do backend é interna: o frontend fala com a API pela rede do
> Docker e ela não é publicada no host.

Mais detalhes em [docs/architecture.md](docs/architecture.md).

---

## ✅ Requisitos

Os requisitos dependem do modo de implantação.

### Com Docker

- **Sistema:** Linux (Ubuntu 24.04 recomendado), ou qualquer sistema com Docker
- **Docker** 20.10+ ([instalação](https://docs.docker.com/engine/install/))
- **Docker Compose** v2+ ([instalação](https://docs.docker.com/compose/install/))
- **Git** (para clonar o repositório)

### Sem Docker (instalação nativa)

- **Sistema:** Ubuntu 22.04 / 24.04 ou Debian 12, x86_64 — **não** serve
  qualquer Linux, porque é preciso o pacote `squid-openssl`
- **Acesso root** e saída para a internet para baixar pacotes
- Nada mais: o instalador coloca Squid, PostgreSQL, nginx, Node e Python

### Hardware mínimo
- **CPU:** 2 núcleos (4 recomendado; com Docker o Squid é compilado ao construir a imagem)
- **RAM:** 2 GB (4 GB recomendado)
- **Disco:** 5 GB livres
- **Rede:** porta 3128 acessível aos clientes do proxy

---

## 🚀 Instalação

**A primeira coisa é escolher o modo de implantação.** São dois, e são
excludentes: numa mesma máquina usa-se um **ou** o outro, nunca os dois.

| | **Modo A — com Docker** | **Modo B — sem Docker (nativo)** |
|---|---|---|
| O que sobe | 4 contêineres | Serviços do sistema, com systemd |
| O que exige | Docker 20.10+ e Compose v2+ | Ubuntu 22.04 / 24.04 ou Debian 12, x86_64 |
| Squid | Compilado ao construir a imagem | Pacote `squid-openssl`; **não compila nada** |
| Quanto demora | 15-30 min na primeira vez, porque compila o Squid | 3-5 min |
| Que privilégios o painel recebe | O socket do Docker, que equivale a root na máquina | Um usuário próprio e três comandos de `sudo` |
| Precisa clonar o repositório | Sim | Não: basta baixar um script |
| Escolha se | Você quer o isolamento dos contêineres e Docker não é problema | A política interna não permite Docker, ou o equipamento já faz de proxy e mais uma camada sobra |

Os dois guias completos, passo a passo, estão em
[docs/installation.pt.md](docs/installation.pt.md) (Docker) e em
[docs/instalacion-nativa.pt.md](docs/instalacion-nativa.pt.md) (nativa).

---

### Modo A — com Docker

Há dois caminhos. Fazem a mesma coisa; a diferença é quem preenche a
configuração.

| | A1: com `install.sh` | A2: manual |
|---|---|---|
| Onde instala | Onde você clonou | Onde você quiser |
| `DB_PASS` e `SECRET_KEY` | São geradas sozinhas | Você as define |
| `PROJECT_DIR` | É preenchida sozinha | **Você precisa ajustá-la** |

#### A1 — com o instalador

Gera as chaves, deixa o `.env` pronto e sobe os contêineres.

```bash
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager
sudo ./install.sh
```

**Instala no diretório onde você clonou**, não num caminho fixo. Se você
executar o script solto, fora de um clone, ele usa `/opt/squid-manager`. Você
também pode impor o caminho:

```bash
sudo INSTALL_DIR=/srv/squid ./install.sh
```

Se já havia uma instalação nesse caminho, ele a atualiza preservando a
configuração; se encontrar alterações locais não confirmadas, faz uma cópia e
para, em vez de sobrescrevê-las.

> Não canalize o script direto para o `bash` a partir da internet: baixe, leia
> e execute, que é o que os comandos acima fazem.

##### Se o servidor sai para a internet por um proxy

O `install.sh` supõe que há saída direta. Quando a rede obriga a passar por um
proxy corporativo, são **três** camadas que precisam ser configuradas
separadamente — o host, o daemon do Docker e os builds — e configurar só uma
deixa a instalação pela metade, normalmente com um `Could not resolve` no meio
de um `apt-get`. Disso cuida um segundo script:

```bash
cp proxy.conf.example proxy.conf
```

Coloque os seus dados em `proxy.conf` (servidor, porta e, se necessário,
usuário e senha; caracteres especiais não precisam de escape) e execute:

```bash
sudo ./install-tras-proxy.sh
```

Ele configura as três camadas, confere que cada uma alcança a internet e só
então roda o `install.sh`. As credenciais ficam em `proxy.conf`, que está no
`.gitignore`: nenhum arquivo do repositório é editado, porque uma alteração
local não confirmada faria o instalador abortar.

Isso é só para **instalar**. Para o Squid sair à internet através do proxy
corporativo depois de instalado, configure pelo painel em **Proxy pai** — veja
[docs/proxy-padre.md](docs/proxy-padre.md).

O procedimento manual equivalente, o que cada passo mexe e o que fazer se o
proxy inspeciona TLS, está em
[docs/instalacion-tras-proxy.md](docs/instalacion-tras-proxy.md).

#### A2 — manual

Escolha este se quiser o projeto em outro caminho ou preferir controlar cada
passo.

```bash
# 1. Clonar o repositório (no caminho que preferir)
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager

# 2. Copiar a configuração de exemplo
cp .env.example .env

# 3. Editar o .env (veja abaixo o que é obrigatório)
nano .env

# 4. Subir o sistema inteiro
docker compose up -d

# 5. Aguardar o Squid compilar (na primeira vez: ~10-15 minutos)
#    Ver o progresso:
docker compose logs -f squid

# 6. Quando aparecer "Accepting HTTP Socket connections", está pronto
```

**Três valores precisam ser ajustados no `.env`, sem exceção:**

```env
DB_PASS=            # obrigatório: openssl rand -hex 16
SECRET_KEY=         # obrigatório: openssl rand -hex 32
PROJECT_DIR=        # o caminho ABSOLUTO onde você acabou de clonar o projeto
```

> **`PROJECT_DIR` é o que se esquece.** Vem com `/opt/squid-manager` como
> exemplo. Se você clonou em outro lugar e não o altera, o sistema sobe e
> funciona normalmente, mas **mudar a porta do proxy pelo painel deixa de
> atualizar o `.env`**, e a porta volta ao valor anterior no próximo
> `docker compose up -d`. Confira com `pwd` e use esse caminho exato.
> (Com o A1 você não precisa se preocupar: o instalador preenche.)

#### Acesso e primeiro login (Docker)

| Serviço | URL |
|----------|-----|
| **Painel web** | http://IP_DO_SERVIDOR:3000 |
| **Proxy Squid** | IP_DO_SERVIDOR:3128 |

Não há senha padrão. O usuário `admin` é criado com uma **senha aleatória** que
aparece **uma única vez** no log do backend:

```bash
docker compose logs backend | grep -A3 "Administrador inicial"
```

Será pedido que você a troque antes de poder usar o painel. Se preferir
defini-la você mesmo, informe `ADMIN_INITIAL_PASSWORD` no `.env` antes do
primeiro arranque.

> A API do backend (porta 8000) não é publicada no host: o painel fala com ela
> pela rede interna do Docker. A documentação interativa (`/docs`) só está
> disponível se você subir com `DEBUG=true` no `.env`.

---

### Modo B — sem Docker (instalação nativa)

Squid, painel, PostgreSQL e nginx rodando como serviços do sistema. **Não é
preciso clonar o repositório, nem editar nenhum `.env`, nem compilar nada**: o
instalador cuida de tudo.

Sobre um Ubuntu 22.04 / 24.04 ou Debian 12 recém-instalado, com acesso root:

```bash
# 1. Baixar o instalador
wget https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/install-nativo.sh

# 2. Ler antes de executar como root (sempre, venha de onde vier)
less install-nativo.sh

# 3. Dar permissão de execução
chmod +x install-nativo.sh

# 4. Executar
sudo ./install-nativo.sh
```

Demora de três a cinco minutos. Ao terminar, imprime a URL do painel, o usuário
e a senha inicial.

**Se você quiser outras portas**, informe-as como variáveis de ambiente (repare
no `-E`, que é o que faz o `sudo` preservá-las):

```bash
WEB_PORT=8080 PROXY_PORT=3130 sudo -E ./install-nativo.sh
```

| Variável | Padrão | O que é |
|---|---|---|
| `WEB_PORT` | `3000` | Porta do painel |
| `PROXY_PORT` | `3128` | Porta do proxy |
| `API_PORT` | `8000` | Porta interna da API (só escuta em localhost) |
| `INSTALL_DIR` | `/opt/squid-manager` | Onde o código fica |
| `APP_USER` | `squidmgr` | Usuário com que o painel roda |

#### O que o instalador faz, em ordem

1. Confere que o sistema é compatível.
2. Instala os pacotes: `squid-openssl`, PostgreSQL, nginx, Node, Python e
   `apache2-utils`. **`squid-openssl`, não `squid`**: o pacote puro é a variante
   GnuTLS, sem SSL bump e sem gerador de certificados.
3. Cria o usuário `squidmgr`, com `proxy` como grupo primário.
4. Clona o código em `/opt/squid-manager`.
5. Cria o banco de dados PostgreSQL.
6. Gera a CA para o SSL Bump e instala o helper de autenticação.
7. Escreve um sudoers com **três comandos literais**, sem curingas.
8. Prepara o ambiente Python, o `.env` e a unidade do systemd.
9. Compila o painel web e configura o nginx.
10. Sobe os serviços e confere que respondem.

#### Acesso e primeiro login (nativo)

O instalador termina imprimindo exatamente isto:

```
  Panel:    http://IP_DO_SERVIDOR:3000
  Proxy:    IP_DO_SERVIDOR:3128
  Usuario:  admin
  Clave:    <senha gerada ao acaso>
```

Essa senha **não é mostrada de novo**, e o painel vai pedir que você a troque no
primeiro acesso. Se você a perder antes de entrar, ela está no log:

```bash
journalctl -u squidmanager | grep -A3 "Administrador inicial"
```

Para operar o serviço depois:

```bash
systemctl status squid squidmanager nginx    # estado
journalctl -u squidmanager -f                # registros do painel
```

As diferenças de comportamento em relação ao Docker — onde a porta vive, como o
tráfego é medido, que estado o painel mostra — estão em
[docs/instalacion-nativa.pt.md](docs/instalacion-nativa.pt.md).

---

### Depois de instalar, em qualquer dos dois modos

**1. Abra a porta do proxy no firewall do servidor.** Nem o instalador nem o
painel fazem isso:

```bash
sudo ufw allow 3128/tcp
```

Sem essa regra o Squid funciona mas os clientes não chegam, e o sintoma é uma
conexão que fica pendurada sem nenhuma mensagem de erro.

**2. Crie o primeiro usuário do proxy**, em *Usuários → Novo usuário*. Até lá
ninguém navega: o proxy exige credenciais desde o primeiro minuto e ainda não há
nenhuma. É de propósito, e está explicado acima em
[Primeiros passos](#-primeiros-passos).

---

## 🔄 Atualizar

```bash
cd /caminho/para/squid-manager && git pull && docker compose up -d --build
```

As migrações do banco de dados são aplicadas sozinhas ao iniciar o backend, e
**sua configuração é preservada**: usuários, regras, portas e certificados não
são tocados.

> **O `--build` não é opcional.** Sem ele, o Docker reutiliza as imagens que já
> tem e o código novo nunca chega a rodar, ainda que o `git pull` tenha dado
> certo. Tudo parece correto — repositório em dia, contêineres iniciados — mas
> você continua na versão anterior.

Numa instalação nativa o passo equivalente é o `npm run build`, exatamente pelo
mesmo motivo: o nginx serve arquivos já compilados.

Para conferir que deu certo:

```bash
cd /caminho/para/squid-manager && git log --oneline -1 && git status --porcelain | wc -l && docker compose ps
```

Você deve ver o commit esperado, **0** arquivos pendentes e os quatro
contêineres em `healthy`.

Veja [docs/actualizacion.md](docs/actualizacion.md) para verificar a revisão do
banco, resolver um `git pull` que aborta, uma migração que falha, ou voltar a
uma versão anterior.

---

## 🔧 Configuração

Tudo é configurado pelo arquivo `.env`:

```env
# PostgreSQL
DB_NAME=squidmanager
DB_USER=squid
DB_PASS=                    # OBRIGATÓRIO: openssl rand -hex 16

# Segurança do painel
SECRET_KEY=                 # OBRIGATÓRIO: openssl rand -hex 32
TOKEN_EXPIRE=480
ADMIN_INITIAL_PASSWORD=     # vazio = aleatória, visível uma vez no log
BCRYPT_COST=12

# Rede e CORS
CORS_ORIGINS=                     # vazio se o painel é servido pela própria URL
TRUSTED_PROXY_HOSTS=frontend      # hosts de quem se aceita X-Forwarded-For
DEBUG=false                       # true expõe /docs sem autenticação

# Implantação
DEPLOY_MODE=docker                # docker (contêiner) ou native (systemd)
NATIVE_SQUID_SERVICE=squid        # nome da unidade systemd, só no modo nativo

# Caminhos
PROJECT_DIR=/opt/squid-manager    # caminho ABSOLUTO deste diretório; o install.sh preenche

# Portas
WEB_PORT=3000
PROXY_PORT=3128                   # porta do proxy; o painel a atualiza ao mudá-la
```

> `PROJECT_DIR` deve apontar para onde o projeto está: o backend a usa para
> recriar o contêiner do Squid com o Compose quando a porta muda. O `install.sh`
> a escreve sozinho; se você instalar à mão ou mover o projeto, ajuste-a.

Para ver todas as opções, veja [docs/configuration.md](docs/configuration.md).

---

## 📚 Primeiros passos

Depois da instalação:

> **Recém-instalado, o proxy não deixa ninguém passar, e é de propósito.**
> O Squid sobe negando tudo exceto `localhost`; o painel substitui isso logo em
> seguida pela configuração definitiva, que exige usuário e senha. Até você
> criar o primeiro usuário do proxy, ninguém navega. Vale para os dois modos de
> implantação: uma instalação recém-feita não pode ficar aberta à rede enquanto
> o dono nem sequer entrou no painel.

1. **Abra o painel** → http://localhost:3000
2. **Faça login** com `admin` e a senha gerada (veja acima)
3. **Troque a senha** quando o painel pedir
4. **Crie um usuário do proxy** → página "Usuários" → "Novo usuário"
5. **Configure seu navegador** com o proxy:
   - IP: `localhost` (ou o IP do servidor)
   - Porta: `3128`
   - Usuário: o que você criou
   - Senha: a que você definiu
6. **Navegue** → seu tráfego passa pelo Squid
7. **Crie uma ACL** → página "ACLs" → "Nova ACL" (ex.: bloquear `.facebook.com`)
8. **Crie uma regra** → página "Regras de acesso" → "Nova regra" → `deny` + sua ACL
9. **Aplique as alterações** → botão "Aplicar alterações" na barra lateral
10. **Teste** → tente acessar o Facebook → deve ser bloqueado

---

## 🔐 SSL Bump (HTTPS)

O SquidManager inclui **SSL Bump**, que permite interceptar e filtrar tráfego
HTTPS.

### Como funciona
1. O Squid gera uma **CA raiz** automaticamente na primeira inicialização
2. Para cada conexão HTTPS, o Squid gera um certificado dinâmico assinado por essa CA
3. O Squid descriptografa o tráfego, aplica as regras (ACLs, delay pools) e o criptografa de novo
4. O navegador do cliente precisa confiar na CA do Squid

Os domínios que não devem ser interceptados (bancos, saúde, aplicativos com
*certificate pinning*) podem ser excluídos da descriptografia em
**Configuração → Segurança → domínios excluídos**.

### Para habilitá-lo nos clientes
1. Abra o painel → **"Certificado"**
2. Baixe o arquivo `squidmanager-ca.crt` (ou o instalador do seu sistema)
3. Instale no repositório de **"Autoridades de Certificação Raiz Confiáveis"** do sistema/navegador
4. Reinicie o navegador

Para instruções por sistema operacional, veja [docs/ssl-bump.md](docs/ssl-bump.md).

---

## 🖥️ Painel web

O painel se organiza em três grupos:

| Grupo | Seção | Função |
|-------|---------|---------|
| **Vigilância** | Painel | Estado do proxy, tráfego em tempo real, principais usuários e domínios |
| | Registros | Visualizador do access.log, com filtros e alertas de força bruta |
| | Auditoria | Registro de todas as alterações feitas |
| **Políticas** | Usuários | Gerenciamento de usuários do proxy |
| | Grupos | Agrupa usuários e aplica políticas ao grupo inteiro |
| | ACLs | Gerenciamento de listas de controle de acesso |
| | Regras de acesso | Gerenciamento de regras `http_access` com reordenação |
| | Largura de banda | Gerenciamento de delay pools (limitação de velocidade) |
| **Sistema** | LDAP | Configuração LDAP / Active Directory |
| | Certificado | Download da CA e instaladores por sistema operacional |
| | Configuração | Parâmetros gerais do Squid |
| | Notificações | Alertas por e-mail e Telegram |
| | Backup e migração | Exportar/restaurar configuração, importar um squid.conf |
| | Administradores | Gerenciamento das contas do painel (só superadmin) |

---

## 🔌 API REST

**A documentação interativa não é acessível de fora do servidor.** A porta 8000
não é publicada no host, então `http://SEU_SERVIDOR:8000/docs` nunca responde —
e numa máquina com outros serviços você poderia acabar vendo a API de outro
contêiner. Além disso, ela só é registrada com `DEBUG=true`; com o valor padrão
retorna 404.

Se você precisar consultá-la:

```bash
# 1. DEBUG=true no .env e recriar o backend
docker compose up -d --force-recreate backend
```

```bash
# 2. Do próprio servidor, contra o IP do contêiner
curl http://$(docker inspect squidmgr-backend --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'):8000/openapi.json
```

Abrir a interface do Swagger no seu navegador exige um túnel SSH até esse IP do
contêiner, já que o servidor o alcança mas a sua máquina não.

> Volte a deixar `DEBUG=false` ao terminar: essa rota é servida sem
> autenticação.

O painel usa a API pelo nginx, em `/api/`, e esse caminho **está** publicado —
é o que responde na porta do painel.

### Idioma das respostas

As mensagens de erro voltam em **espanhol, inglês ou português** conforme o
cabeçalho `Accept-Language` da requisição. Sem cabeçalho, ou com um idioma não
suportado, responde em espanhol. Veja [docs/idiomas.md](docs/idiomas.md).

### Principais endpoints

| Método | Endpoint | Descrição |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login do admin (JWT) |
| GET | `/api/proxy-users/` | Listar usuários do proxy |
| POST | `/api/proxy-users/` | Criar usuário |
| GET | `/api/groups/` | Listar grupos de usuários |
| GET | `/api/acls/` | Listar ACLs |
| POST | `/api/acls/` | Criar ACL |
| GET | `/api/access-rules/` | Listar regras |
| PUT | `/api/access-rules/reorder` | Reordenar regras |
| GET | `/api/delay-pools/` | Listar delay pools |
| GET | `/api/squid/settings` | Ver a configuração |
| POST | `/api/squid/apply` | Validar e aplicar alterações no Squid |
| GET | `/api/squid/status` | Estado do Squid |
| GET | `/api/squid/ca-cert` | Baixar o certificado CA |
| GET | `/api/ldap/config` | Ver a configuração LDAP |
| POST | `/api/ldap/test` | Testar a conexão LDAP |
| GET | `/api/backup/export` | Exportar toda a configuração para JSON |
| GET | `/api/panel/dashboard` | Métricas do painel |
| GET | `/api/logs/access` | Consultar o access.log |
| GET | `/api/audit/` | Listar o log de auditoria |

> As métricas são servidas **tanto** em `/api/metrics/*` quanto em
> `/api/panel/*` — os mesmos endpoints. Use `/api/panel` a partir de um
> navegador: bloqueadores de anúncios e filtros de privacidade cortam qualquer
> URL que contenha "metrics" por associá-la a telemetria, e a requisição nem
> chega a sair do navegador.

São 14 routers e 72 endpoints no total. Para a documentação completa, veja
[docs/api-reference.md](docs/api-reference.md).

---

## 📚 Documentação

A documentação completa está em espanhol. Traduzido para o português:

- [Guia de instalação](docs/installation.pt.md)
- [Instalação nativa, sem Docker](docs/instalacion-nativa.pt.md)

Em espanhol:

| Documento | Descrição |
|-----------|-------------|
| [docs/idiomas.md](docs/idiomas.md) | Idiomas do painel, da API e do proxy |
| [docs/configuration.md](docs/configuration.md) | Todas as opções de configuração |
| [docs/architecture.md](docs/architecture.md) | Arquitetura técnica detalhada |
| [docs/authentication.md](docs/authentication.md) | Contas, sessões, papéis e grupos |
| [docs/ssl-bump.md](docs/ssl-bump.md) | Guia de SSL Bump e certificados CA |
| [docs/proxy-padre.md](docs/proxy-padre.md) | Sair à internet por outro proxy |
| [docs/instalacion-tras-proxy.md](docs/instalacion-tras-proxy.md) | Instalar num servidor atrás de um proxy |
| [docs/actualizacion.md](docs/actualizacion.md) | Como atualizar, verificar e voltar atrás |
| [docs/backup-restore.md](docs/backup-restore.md) | Backup, restauração e migração |
| [docs/production.md](docs/production.md) | Implantação em produção |
| [docs/api-reference.md](docs/api-reference.md) | Documentação completa da API |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Como contribuir |

---

## 🛠️ Solução de problemas

### O contêiner do Squid não inicia
```bash
docker compose logs squid
```
Na primeira vez o Squid é compilado do código-fonte (~10-15 minutos). Aguarde
até ver "Accepting HTTP Socket connections".

### O proxy não bloqueia sites HTTPS
Você precisa de SSL Bump. Veja [docs/ssl-bump.md](docs/ssl-bump.md).

### O navegador mostra aviso de certificado
Instale o certificado CA pelo painel → "Certificado".

### Não consigo acessar o painel
```bash
docker compose ps              # verificar que todos os contêineres estão UP
docker compose logs backend    # ver erros do backend
```

### O painel fica em "Carregando métricas…"

Quase sempre é um bloqueador de anúncios. O painel pede `/api/panel/dashboard`
justamente para evitar isso, mas um filtro personalizado agressivo ainda pode
cortá-lo. Verifique no console do navegador se aparece `ERR_BLOCKED_BY_CLIENT`
e, se for o caso, libere o endereço do painel no seu bloqueador.

### Reinstalei e o backend não sobe: "password authentication failed"

O volume de dados da instalação anterior sobreviveu. A senha de um banco de
dados já criado **não muda ao colocar outra no `.env`**: o
`POSTGRES_PASSWORD` só tem efeito na primeira vez, quando o PostgreSQL cria o
banco vazio. Se o volume já existia, ele mantém a senha original e o backend,
que usa a nova, não consegue entrar.

Atenção ao reinstalar em outro caminho: o Compose nomeia os volumes pelo **nome
do diretório** do projeto, então duas instalações em caminhos diferentes mas com
a mesma pasta (`squid-manager`) compartilham volume.

```bash
# Ver se existe o volume de uma instalação anterior
docker volume ls | grep pgdata
```

Duas saídas:

```bash
# 1) Começar do zero. APAGA TODOS OS DADOS (usuários, regras, histórico)
docker compose down -v && docker compose up -d
```

```bash
# 2) Preservar os dados: recupere a DB_PASS com a qual o banco foi criado,
#    coloque-a no .env e suba de novo
docker compose up -d
```

O instalador verifica isso antes de gerar um `.env` novo e para se encontrar um
volume órfão, em vez de deixar o sistema pela metade.

### Não lembro a senha inicial do admin
Troque-a por uma sessão de banco de dados, ou verifique se ainda está no log:
```bash
docker compose logs backend | grep -A3 "Administrador inicial"
```

### Sair à internet por outro proxy (pai e filho)

Em muitas empresas o firewall fecha a saída direta e todo o tráfego precisa
passar pelo proxy corporativo. O SquidManager pode ficar atrás de outro proxy, e
a configuração é feita em **Painel → Proxy pai**.

A divisão de papéis é o que faz funcionar:

| | Filho (o de baixo) | Pai (o de cima) |
|---|---|---|
| Autentica usuários | **Sim** | Não: confia no filho |
| Filtra por domínio | **Sim** | Não |
| Intercepta HTTPS | **Sim** | **Não**: apenas tunela |
| Sai à internet | Não: pelo pai | **Sim** |

Encadear dois proxies exige quatro ajustes, e faltando qualquer um não funciona:

1. **No filho**: servidor, porta e — se exigidas — credenciais do pai
2. **No filho**: o certificado CA do pai, se o pai também intercepta HTTPS
3. **No pai**: `trusted_sources` com o IP do filho, para que não lhe peça credenciais
4. **No pai**: `ssl_bump_enabled = false`, porque só um dos dois pode interceptar HTTPS

Se ambos forem SquidManager, também precisam de um `visible_hostname`
diferente: o Squid rejeita como laço tudo que já leve o seu nome no cabeçalho
`Via`.

Para conferir que funciona, a última coluna do log de acessos do filho muda de
`HIER_DIRECT` para `FIRSTUP_PARENT`.

> **Guia completo em [docs/proxy-padre.md](docs/proxy-padre.md)**: o porquê de
> cada peça, a configuração passo a passo, e uma tabela para identificar pelo
> sintoma qual dos quatro ajustes está faltando — todos produzem erros que não
> mencionam a causa.

### Isentar um grupo da interceptação de HTTPS

Em **Grupos**, cada grupo tem a caixa **"Não interceptar o HTTPS deste grupo"**.
Seus membros navegam com o tráfego criptografado de ponta a ponta.

Serve para dois casos comuns:

- **Equipamentos onde o certificado não pode ser instalado**: celulares pessoais, BYOD, dispositivos de visitantes
- **Ferramentas que quebram ao serem interceptadas**: git, npm, docker e qualquer aplicativo com *certificate pinning*

> **Isentar da descriptografia não é isentar da filtragem.** O bloqueio por
> domínio atua sobre o SNI, antes de descriptografar, então continua valendo
> para esses usuários. Eles também continuam se autenticando e sendo
> registrados. O que se perde é a inspeção da URL completa e do conteúdo.

Para conferir que está funcionando, no log de acessos as conexões HTTPS deles
aparecem como `TCP_TUNNEL/200 CONNECT`, sem a requisição descriptografada
(`GET https://…`) que se vê nos demais.

### Origens que não precisam se autenticar

Em **Configuração → Segurança**, o ajuste `trusted_sources` aceita IPs ou redes
que podem navegar sem credenciais:

```
trusted_sources = 203.0.113.10 198.51.100.0/24
```

Pensado para um proxy filho que já autentica seus próprios usuários. Vazio por
padrão: todo mundo precisa se autenticar.

> É uma isenção de autenticação: indique a origem específica. Se esse IP for uma
> saída NAT compartilhada, **qualquer equipamento atrás dele fica isento**.

### Usar seus próprios servidores DNS (um Pi-hole, por exemplo)

O Squid resolve os nomes por conta própria, então você pode indicar a quais
servidores perguntar e fazer a navegação do proxy herdar a filtragem de um
Pi-hole, um AdGuard ou o DNS interno da sua empresa.

1. Painel → Configuração → `dns_nameservers` → os IPs separados por espaços
2. Clique em **Testar** para verificar que respondem
3. Salvar → Aplicar alterações

```
dns_nameservers 172.27.0.1
```

Vazio = o Squid usa a resolução do sistema (o comportamento padrão).

**Somente IPs, não nomes de host.** O Squid precisa poder perguntar sem resolver
nada antes, que é justamente o que ele ainda não consegue fazer.

> **Com mais de um servidor, a filtragem deixa de ser garantida.** O Squid
> distribui as consultas entre todos os servidores da lista, não os usa como
> reserva: adicionar um DNS público ao lado do Pi-hole faz com que a parcela de
> consultas que cair no público seja resolvida sem filtro. Para que **tudo**
> passe pelo filtro, deixe um único servidor.

Ao aplicar, verifica-se que os servidores respondem de verdade e a alteração é
rejeitada se não responderem. É proposital: um DNS inalcançável não quebra um
site, para de resolver todos de uma vez, e o sintoma não aponta para a causa.

Se o Pi-hole roda como contêiner na mesma máquina, use o IP do gateway da rede
Docker dele (`docker network inspect`), não `127.0.0.1`: dentro do contêiner do
Squid esse endereço é o próprio Squid.

### Mudar a porta do proxy
1. Painel → Configuração → `http_port` → colocar a porta nova → Salvar
2. Painel → Aplicar alterações

Não é preciso editar nenhum arquivo à mão. No modo Docker o backend atualiza o
`PROXY_PORT` no `.env` e recria o contêiner com o Docker Compose, então a
alteração também sobrevive a um `docker compose up -d` ou a um reinício da
máquina. No modo nativo a porta vai direto para o `squid.conf` e o serviço é
reiniciado.

**Abra a porta nova no firewall do servidor** e feche a anterior se não for mais
usada:

```bash
sudo ufw allow 8128/tcp && sudo ufw delete allow 3128/tcp
```

O painel não gerencia o firewall. Sem essa regra o Squid escuta corretamente mas
os clientes não chegam, e o sintoma é uma conexão que fica pendurada sem
nenhuma mensagem de erro.

> No modo Docker o Squid sempre escuta na **3128 dentro do contêiner**; a porta
> que você escolhe é a que o Docker publica para fora. Por isso o `squid.conf`
> mostra `http_port 3128` mesmo que os clientes se conectem a outra porta: a
> porta vive num único lugar (`PROXY_PORT`) e assim não pode dessincronizar.

---

## 📝 Licença

Apache-2.0 — veja [LICENSE](LICENSE) para mais detalhes.

---

## 🤝 Contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md) para saber como contribuir com o
projeto.

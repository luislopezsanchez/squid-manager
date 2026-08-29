# Guia de Instalação — SquidManager

**[Español](installation.md) · [English](installation.en.md) · Português**

Este guia leva você passo a passo de um servidor vazio até um SquidManager
funcionando.

> **Este é o guia da implantação com Docker.** Se você não quer Docker nessa
> máquina, há um segundo modo em que tudo roda como serviços do sistema:
> [instalacion-nativa.pt.md](instalacion-nativa.pt.md). Escolhe-se um dos dois;
> na mesma máquina eles não convivem.

> A versão em espanhol, [installation.md](installation.md), é a fonte de
> verdade. Se houver divergência, o espanhol está certo.

---

## Pré-requisitos

### Sistema operacional
- Ubuntu 20.04 / 22.04 / 24.04 (recomendado)
- Qualquer Linux com Docker funcionando

### Hardware mínimo
| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| CPU | 2 núcleos | 4 núcleos |
| RAM | 2 GB | 4 GB |
| Disco | 5 GB livres | 10 GB |
| Swap | 2 GB | 4 GB |

> ⚠️ A compilação do Squid a partir do código-fonte exige pelo menos 2 GB de RAM
> mais 2 GB de swap. Com menos, a compilação pode falhar.

### Software necessário
- **Docker** 20.10 ou superior
- **Docker Compose** v2 ou superior
- **Git**

### Instalar o Docker (se você não o tiver)

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verificar
docker --version
docker compose version
```

---

## Duas formas de instalar

> **O servidor sai à internet por um proxy?** Nenhuma das duas formas abaixo
> funciona como está: são necessárias três configurações de proxy diferentes
> antes de começar. Veja
> [instalacion-tras-proxy.md](instalacion-tras-proxy.md) (em espanhol).

Fazem a mesma coisa; a diferença é quem preenche a configuração.

| | Com `install.sh` | Manual |
|---|---|---|
| Onde instala | Onde você clonou | Onde você quiser |
| `DB_PASS` e `SECRET_KEY` | São geradas sozinhas | Você as define |
| `PROJECT_DIR` | É preenchida sozinha | **Você precisa ajustá-la** |

### Com o instalador

```bash
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager
sudo ./install.sh
```

O script gera as chaves, deixa o `.env` pronto e sobe os contêineres.

**Instala no diretório onde você clonou.** Se você executar o script solto, fora
de um clone, ele usa `/opt/squid-manager`. Para impor outro caminho:

```bash
sudo INSTALL_DIR=/srv/squid ./install.sh
```

Se já havia uma instalação nesse caminho, ele a atualiza preservando a
configuração existente. Se encontrar alterações locais não confirmadas, faz uma
cópia ao lado do projeto e para, em vez de deixar o `git pull` sobrescrevê-las.

> Não canalize o script direto para o `bash` a partir da internet: baixe, leia e
> execute, que é o que os comandos acima fazem.

Se você usou o instalador, pode pular para o
[Passo 4](#passo-4-aguardar-a-compilação-do-squid). O resto deste guia descreve
a instalação manual.

---

## Instalação manual, passo a passo

### Passo 1: Clonar o repositório

```bash
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager
```

Você pode cloná-lo onde quiser. Anote o caminho: ele é necessário no passo
seguinte.

### Passo 2: Configurar as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o arquivo `.env` com os seus valores:

```bash
nano .env
```

**`DB_PASS` e `SECRET_KEY` são obrigatórios** — o `docker-compose.yml` se recusa
a subir sem eles. Gere ambos com:

```bash
openssl rand -hex 16   # para DB_PASS
openssl rand -hex 32   # para SECRET_KEY
```

Se você deixar `ADMIN_INITIAL_PASSWORD` vazio (o padrão), o backend gera uma
senha aleatória para a conta `admin` na primeira vez que sobe; se preferir
escolhê-la, informe-a ali antes do primeiro `docker compose up`.

**`PROJECT_DIR` é o terceiro valor que precisa ser ajustado**, e o mais
esquecido porque o sistema sobe do mesmo jeito sem ele:

```bash
pwd    # copie este caminho
```

```env
PROJECT_DIR=/o/caminho/que/o/pwd/deu
```

Vem com `/opt/squid-manager` como exemplo, que é onde o `install.sh` instala. Se
você clonou em outro lugar e não o altera, tudo funciona normalmente exceto uma
coisa: **mudar a porta do proxy pelo painel deixa de atualizar o `.env`**, e a
porta volta ao valor anterior no próximo `docker compose up -d`, deixando o
proxy inalcançável sem nenhum aviso.

O backend usa esse caminho para recriar o contêiner do Squid com o Docker
Compose, e precisa vê-lo no mesmo local que ele tem no servidor.

### Passo 3: Subir os contêineres

```bash
docker compose up -d
```

Isso cria 4 contêineres:

| Contêiner | Serviço | Porta publicada | Descrição |
|-----------|----------|-------------------|-------------|
| squidmgr-db | PostgreSQL 16 | nenhuma (interna) | Banco de dados |
| squidmgr-backend | FastAPI | nenhuma (interna) | API REST |
| squidmgr-proxy | Squid 6.12 | 3128 | Proxy com SSL Bump |
| squidmgr-frontend | React + Nginx | 3000 | Painel web |

> O backend não publica mais a porta 8000 no host: o frontend fala com ele pela
> rede interna do Docker. Se você precisar acessar a API diretamente (para
> depurar, por exemplo), use `docker exec` ou publique a porta você mesmo num
> override de desenvolvimento.

### Passo 4: Aguardar a compilação do Squid

**⚠️ Importante:** na primeira vez, o contêiner do Squid compila o Squid 6.12 a
partir do código-fonte com suporte a SSL Bump (OpenSSL). Isso leva **10-15
minutos** dependendo do hardware.

Você pode acompanhar o progresso:

```bash
docker compose logs -f squid
```

Quando aparecer esta mensagem, está pronto:
```
Accepting HTTP Socket connections at conn3 local=[::]:3128
listening port: 3128
```

Pressione `Ctrl+C` para sair dos logs (o contêiner continua rodando).

### Passo 5: Verificar que tudo funciona

```bash
# Verificar que os 4 contêineres estão UP
docker compose ps

# Testar o backend de dentro do próprio contêiner
# (a porta não está publicada no host)
docker exec squidmgr-backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"
# Deve responder: {"status":"ok"}

# Testar o painel web
curl -o /dev/null -w "%{http_code}" http://localhost:3000/
# Deve responder: 200
```

### Passo 6: Acessar o painel

1. Abra o navegador em **http://IP_DO_SERVIDOR:3000**
2. Consulte a senha gerada para o `admin`:
   ```bash
   docker compose logs backend | grep -A3 "Administrador inicial"
   ```
   (Se você definiu `ADMIN_INITIAL_PASSWORD` no `.env`, use essa.)
3. Faça login com `admin` e essa senha
4. O painel pedirá que você a **troque** antes de deixá-lo entrar — é
   obrigatório no primeiro acesso
5. Pronto, você está dentro.

---

## Configuração pós-instalação

### Trocar a senha do admin

Faça isso **sempre pelo painel**: entre → ícone de chave na barra lateral →
"Alterar senha". Trocar a senha assim invalida qualquer sessão aberta em outros
navegadores.

> Não a troque escrevendo direto no banco de dados nem com um script que apenas
> atualize `password_hash`: o sistema também registra quando a senha foi
> trocada, para poder encerrar sessões antigas, e uma troca manual que pule esse
> passo deixa as proteções de sessão órfãs.

### Criar um usuário do proxy

Pelo painel:
1. Vá em **"Usuários"**
2. Clique em **"Novo usuário"**
3. Informe usuário e senha (mínimo 8 caracteres)
4. Clique em **"Criar usuário"**

### Configurar o proxy nos clientes

**No navegador do cliente:**
- Tipo: proxy HTTP
- Endereço: IP_DO_SERVIDOR
- Porta: 3128
- Usuário: o que você criou
- Senha: a que você definiu

**Ou por linha de comando (Linux):**
```bash
export http_proxy=http://usuario:senha@IP_DO_SERVIDOR:3128
export https_proxy=http://usuario:senha@IP_DO_SERVIDOR:3128
```

---

## Desinstalação

```bash
# Parar e remover os contêineres
docker compose down

# Remover os volumes (apaga todos os dados!)
docker compose down -v

# Remover as imagens
docker rmi squid-manager-backend squid-manager-frontend squid-manager-squid
```

---

## Atualização

```bash
git pull origin main
docker compose build
docker compose up -d
```

O esquema do banco de dados é gerenciado com o Alembic: as migrações pendentes
são aplicadas automaticamente ao iniciar o backend. Se você estiver atualizando
uma instalação muito antiga (anterior à adoção do Alembic), confira o log do
backend após o `up -d`:

```bash
docker compose logs backend | grep -i alembic
```

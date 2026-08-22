# Contribuir a SquidManager

¡Gracias por tu interés en contribuir! Este documento explica cómo hacerlo.

---

## 🚀 Empezar

### Requisitos de desarrollo
- Docker + Docker Compose
- Git
- Editor de código (VS Code recomendado)

### Configurar entorno de desarrollo

```bash
# Fork el repositorio en GitHub
# Clona tu fork
git clone https://github.com/TU_USUARIO/squid-manager.git
cd squid-manager

# Añade el upstream
git remote add upstream https://github.com/luislopezsanchez/squid-manager.git

# Levanta el entorno
cp .env.example .env
docker compose up -d
```

### Desarrollo del backend

El backend tiene hot-reload habilitado. Los cambios en `backend/app/` se recargan automáticamente:

```bash
# Ver logs del backend
docker compose logs -f backend

# Instalar nueva dependencia
docker exec squidmgr-backend pip install nuevo-paquete
# Luego añadir a backend/requirements.txt
```

### Desarrollo del frontend

El frontend se sirve estáticamente via Nginx. Para desarrollo con hot-reload:

```bash
cd frontend
npm install
npm run dev
# Vite sirve en http://localhost:5173
# La API se proxy a http://localhost:8000
```

Para rebuild del contenedor frontend después de cambios:

```bash
docker compose build frontend
docker compose up -d frontend
```

---

## 📝 Estructura del código

### Backend
- **Models** (`app/models/`): Definiciones de tablas SQLAlchemy
- **Schemas** (`app/schemas/`): Validación Pydantic para requests/responses
- **Routes** (`app/routes/`): Endpoints REST de FastAPI
- **Services** (`app/services/`): Lógica de negocio
- **Templates** (`app/templates/`): Template Jinja2 para generar squid.conf

### Frontend
- **Pages** (`src/pages/`): Una página por sección del panel
- **Components** (`src/components/`): Componentes reutilizables (Layout, Toast)
- **API** (`src/api/client.ts`): Cliente HTTP con todos los endpoints

---

## 🔄 Flujo de trabajo

1. Crea un branch: `git checkout -b feature/mi-feature`
2. Haz tus cambios
3. Testea: `docker compose up -d` y prueba manualmente
4. Commit: `git commit -m "feat: descripción del cambio"`
5. Push: `git push origin feature/mi-feature`
6. Abre un Pull Request en GitHub

### Convención de commits

Usamos [Conventional Commits](https://www.conventionalcommits.org/):

| Tipo | Descripción |
|------|-------------|
| `feat:` | Nueva funcionalidad |
| `fix:` | Corrección de bug |
| `docs:` | Cambios en documentación |
| `refactor:` | Refactorización de código |
| `style:` | Cambios de formato/estilo |
| `test:` | Añadir o modificar tests |
| `chore:` | Tareas de mantenimiento |

Ejemplo: `feat: añadir página de logs en tiempo real`

---

## 🧪 Testing

### Tests del backend
```bash
docker exec squidmgr-backend pytest
```

### Tests manuales
Verificar que las funcionalidades principales siguen funcionando:
1. Login del panel
2. Crear/editar/eliminar usuarios
3. Crear/editar/eliminar ACLs
4. Crear/editar/eliminar reglas
5. Aplicar cambios
6. Navegar a través del proxy

---

## 📋 Checklist antes de un Pull Request

- [ ] El código funciona localmente
- [ ] Los contenedores levantan sin errores
- [ ] No se incluyen credenciales ni secrets
- [ ] Se actualizó la documentación si es necesario
- [ ] Se actualizó el CHANGELOG.md
- [ ] Los commits siguen la convención

---

## 🐛 Reportar bugs

Si encuentras un bug, abre un [Issue](https://github.com/luislopezsanchez/squid-manager/issues) con:

1. **Descripción** del problema
2. **Pasos para reproducirlo**
3. **Comportamiento esperado** vs **comportamiento actual**
4. **Logs** (`docker compose logs`)
5. **Versión** de SquidManager

---

## 💡 Sugerir funcionalidades

Abre un [Issue](https://github.com/luislopezsanchez/squid-manager/issues) con la etiqueta `enhancement` describiendo:
- Qué funcionalidad te gustaría
- Por qué sería útil
- Cómo te imaginas que funcionaría

---

## 📄 Licencia

Al contribuir, aceptas que tus cambios se publiquen bajo la licencia Apache-2.0.
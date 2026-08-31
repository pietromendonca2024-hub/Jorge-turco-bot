
import os
import io
import json
import time
import sqlite3
import asyncio
import traceback
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

# ============================================================
# BOT FACÇÃO PRO — REBUILD DO ZERO
# Interface inspirada nos vídeos enviados:
# - /gerenciar abre um dashboard privado
# - cada sistema possui tela própria de configuração
# - Status / Logs / Cargos / URL / opções específicas
# - painéis públicos usam botões + modais
# ============================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID", "")
FAC_NAME = os.getenv("FAC_NAME", "JORGE TURCO")
DB_PATH = os.getenv("DB_PATH", "faccao.db")
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "backups"))
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN não configurado.")

# -------- Discord --------
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.voice_states = True
intents.moderation = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -------- Aparência --------
GOLD = 0xC89B3C
GREEN = 0x57F287
RED = 0xED4245
BLUE = 0x5865F2
GREY = 0x2B2D31
FOOTER = f"{FAC_NAME} • Facção Pro"

# -------- Sistemas --------
SYSTEMS = {
    "registro": {
        "label": "Registro",
        "emoji": "👤",
        "description": "Gerencie o sistema de registro e aprovação de membros.",
        "public_title": "👤 CENTRAL DE REGISTRO",
        "public_description": "Realize seu registro utilizando o botão abaixo. Após o envio, aguarde a análise da liderança.",
    },
    "vendas": {
        "label": "Vendas",
        "emoji": "💵",
        "description": "Configure catálogo, acesso e registros de vendas.",
        "public_title": "💵 CENTRAL DE VENDAS",
        "public_description": "Registre uma nova venda através do botão abaixo.",
    },
    "banco": {
        "label": "Banco",
        "emoji": "🏦",
        "description": "Controle entradas, saídas e saldo da organização.",
        "public_title": "🏦 CENTRAL DO BANCO",
        "public_description": "Utilize os botões abaixo para movimentar ou consultar o banco.",
    },
    "lavagem": {
        "label": "Lavagem",
        "emoji": "💸",
        "description": "Registre operações e calcule taxas automaticamente.",
        "public_title": "💸 CENTRAL DE LAVAGEM",
        "public_description": "Registre uma nova operação de lavagem.",
    },
    "encomendas": {
        "label": "Encomendas",
        "emoji": "📦",
        "description": "Gerencie pedidos, responsáveis e aprovações.",
        "public_title": "📦 CENTRAL DE ENCOMENDAS",
        "public_description": "Registre pedidos para aprovação da equipe responsável.",
    },
    "ausencia": {
        "label": "Ausência",
        "emoji": "⌛",
        "description": "Solicitações de ausência com aprovação/reprovação.",
        "public_title": "⌛ CENTRAL DE AUSÊNCIAS",
        "public_description": "Solicite uma ausência e aguarde a análise da liderança.",
    },
    "farm": {
        "label": "Farm",
        "emoji": "📦",
        "description": "Farm com comprovação, aprovação e ranking.",
        "public_title": "📦 CENTRAL DE FARM",
        "public_description": "Envie seu farm para aprovação.",
    },
    "bau": {
        "label": "Baús",
        "emoji": "🧰",
        "description": "Baú geral, baú de líder e controle de estoque.",
        "public_title": "🧰 CENTRAL DE BAÚ",
        "public_description": "Registre entradas, retiradas e consulte o estoque.",
    },
    "acoes": {
        "label": "Ações",
        "emoji": "🎯",
        "description": "Organize ações, horários e participantes.",
        "public_title": "🎯 CENTRAL DE AÇÕES",
        "public_description": "Consulte e registre ações da organização.",
    },
}

DEFAULTS = {
    "enabled": False,
    "log_channel_id": None,
    "access_role_ids": [],
    "approver_role_ids": [],
    "embed_url": "",
    "approved_role_id": None,
    "visitor_enabled": False,
    "visitor_role_id": None,
    "name_pattern": "{id} | {nome}",
    "products": [],
    "partner_discount": 0,
    "laundry_rate": 25.0,
    "member_role_id": None,
}

# ============================================================
# BANCO DE DADOS
# ============================================================

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def init_db():
    conn = connect()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            guild_id INTEGER NOT NULL,
            system TEXT NOT NULL,
            data TEXT NOT NULL,
            PRIMARY KEY(guild_id, system)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            identificacao TEXT NOT NULL,
            telefone TEXT,
            recrutador TEXT,
            status TEXT NOT NULL DEFAULT 'pendente',
            reviewer_id INTEGER,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            produto TEXT NOT NULL,
            parceria INTEGER NOT NULL DEFAULT 0,
            quantidade INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total REAL NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS banco (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            valor REAL NOT NULL,
            descricao TEXT,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS lavagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            bruto REAL NOT NULL,
            taxa REAL NOT NULL,
            liquido REAL NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS encomendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            responsavel_id INTEGER NOT NULL,
            descricao TEXT NOT NULL,
            data_hora TEXT NOT NULL,
            destinatario TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pendente',
            reviewer_id INTEGER,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS ausencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            periodo TEXT NOT NULL,
            motivo TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pendente',
            reviewer_id INTEGER,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS farms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            item TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            comprovante TEXT,
            status TEXT NOT NULL DEFAULT 'pendente',
            reviewer_id INTEGER,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS estoque (
            guild_id INTEGER NOT NULL,
            bau TEXT NOT NULL,
            item TEXT NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(guild_id, bau, item)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS estoque_mov (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            bau TEXT NOT NULL,
            tipo TEXT NOT NULL,
            item TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS advertencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            motivo TEXT NOT NULL,
            pontos INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS pontos (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            pontos INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(guild_id, user_id)
        )
    """)

    conn.commit()
    conn.close()

def get_config(guild_id: int, system: str):
    data = dict(DEFAULTS)
    conn = connect()
    row = conn.execute(
        "SELECT data FROM system_config WHERE guild_id=? AND system=?",
        (guild_id, system)
    ).fetchone()
    conn.close()
    if row:
        try:
            saved = json.loads(row["data"])
            if isinstance(saved, dict):
                data.update(saved)
        except Exception:
            pass
    return data

def save_config(guild_id: int, system: str, data: dict):
    conn = connect()
    conn.execute(
        """INSERT INTO system_config(guild_id,system,data) VALUES(?,?,?)
           ON CONFLICT(guild_id,system) DO UPDATE SET data=excluded.data""",
        (guild_id, system, json.dumps(data, ensure_ascii=False))
    )
    conn.commit()
    conn.close()

def update_config(guild_id: int, system: str, **changes):
    cfg = get_config(guild_id, system)
    cfg.update(changes)
    save_config(guild_id, system, cfg)
    return cfg

def add_points(guild_id: int, user_id: int, amount: int):
    conn = connect()
    conn.execute(
        """INSERT INTO pontos(guild_id,user_id,pontos) VALUES(?,?,?)
           ON CONFLICT(guild_id,user_id) DO UPDATE SET pontos=pontos+excluded.pontos""",
        (guild_id, user_id, amount)
    )
    conn.commit()
    conn.close()

# ============================================================
# HELPERS
# ============================================================

def embed(title, description="", color=GOLD, image_url=""):
    e = discord.Embed(title=title, description=description, color=color)
    if image_url:
        e.set_image(url=image_url)
    e.set_footer(text=FOOTER)
    return e

def role_mentions(guild, ids):
    values = []
    for rid in ids or []:
        role = guild.get_role(int(rid))
        if role:
            values.append(role.mention)
    return ", ".join(values) if values else "Nenhum cargo configurado."

def channel_mention(guild, cid):
    if not cid:
        return "Nenhum canal configurado."
    ch = guild.get_channel(int(cid))
    return ch.mention if ch else "Canal não encontrado."

def role_mention(guild, rid):
    if not rid:
        return "Nenhum cargo configurado."
    role = guild.get_role(int(rid))
    return role.mention if role else "Cargo não encontrado."

def is_admin(member: discord.Member):
    return member.guild_permissions.administrator

def has_access(member: discord.Member, system: str):
    if is_admin(member):
        return True
    cfg = get_config(member.guild.id, system)
    allowed = {int(x) for x in cfg.get("access_role_ids", [])}
    if not allowed:
        return False
    return any(r.id in allowed for r in member.roles)

def can_approve(member: discord.Member, system: str):
    if is_admin(member):
        return True
    cfg = get_config(member.guild.id, system)
    allowed = {int(x) for x in cfg.get("approver_role_ids", [])}
    if not allowed:
        return False
    return any(r.id in allowed for r in member.roles)

def enabled(guild_id: int, system: str):
    return bool(get_config(guild_id, system).get("enabled"))

async def log_event(guild, system, title, description, color=GOLD):
    cfg = get_config(guild.id, system)
    cid = cfg.get("log_channel_id")
    if not cid:
        return
    ch = guild.get_channel(int(cid))
    if isinstance(ch, discord.TextChannel):
        try:
            await ch.send(embed=embed(title, description, color))
        except Exception:
            pass

async def deny(interaction, text="❌ Você não possui permissão para utilizar esta função."):
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)

def money(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_money(text):
    text = str(text).strip().replace("R$", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(".", "")
    return float(text)

def parse_int(text):
    return int(str(text).replace(".", "").replace(",", "").strip())

# ============================================================
# DASHBOARD DE CONFIGURAÇÃO — ESTILO DO VÍDEO
# ============================================================

def home_embed(guild: discord.Guild):
    e = embed(
        f"⚙️ Gerenciamento • {FAC_NAME}",
        "Selecione abaixo qual sistema deseja configurar.\n"
        "Todas as alterações são salvas automaticamente."
    )
    for key, meta in SYSTEMS.items():
        cfg = get_config(guild.id, key)
        status = "🟢 Ligado" if cfg["enabled"] else "🔴 Desligado"
        e.add_field(
            name=f"{meta['emoji']} {meta['label']} • {status}",
            value=meta["description"],
            inline=False
        )
    return e

def system_embed(guild: discord.Guild, system: str):
    meta = SYSTEMS[system]
    cfg = get_config(guild.id, system)

    e = embed(
        f"{meta['emoji']} Sistema de {meta['label']}",
        meta["description"]
    )

    status = "Ativado" if cfg["enabled"] else "Desativado"
    e.add_field(
        name="👁️ Status",
        value=f"Ative ou desative o sistema.\n**Status atual:** `{status}`",
        inline=False
    )
    e.add_field(
        name="🖥️ Canal de Logs",
        value=f"Escolha onde os logs serão enviados.\n**Canal atual:** {channel_mention(guild, cfg['log_channel_id'])}",
        inline=False
    )
    e.add_field(
        name="🔐 Cargos de Acesso",
        value=f"Cargos que podem utilizar o sistema.\n**Cargos atuais:** {role_mentions(guild, cfg['access_role_ids'])}",
        inline=False
    )

    if system in {"registro", "encomendas", "ausencia", "farm"}:
        e.add_field(
            name="✅ Cargos de Aprovadores",
            value=f"Cargos que podem aprovar/reprovar solicitações.\n**Cargos atuais:** {role_mentions(guild, cfg['approver_role_ids'])}",
            inline=False
        )

    if system == "registro":
        e.add_field(
            name="🪪 Padrão de Nome",
            value=f"Use `{{id}}` e `{{nome}}`.\n**Padrão atual:** `{cfg['name_pattern']}`",
            inline=False
        )
        e.add_field(
            name="🎭 Cargo ao ser aprovado",
            value=f"Cargo atribuído após aprovação.\n**Cargo atual:** {role_mention(guild, cfg['approved_role_id'])}",
            inline=False
        )
        visitor_status = "Ativado" if cfg["visitor_enabled"] else "Desativado"
        e.add_field(
            name="🧳 Cargo de Visitante",
            value=f"**Status:** `{visitor_status}`\n**Cargo:** {role_mention(guild, cfg['visitor_role_id'])}",
            inline=False
        )

    if system == "vendas":
        products = cfg.get("products", [])
        e.add_field(
            name="📦 Catálogo de Produtos",
            value=f"Produtos cadastrados: **{len(products)}**\n"
                  f"Desconto parceria: **{cfg.get('partner_discount', 0)}%**",
            inline=False
        )

    if system == "lavagem":
        e.add_field(
            name="📊 Taxa de Lavagem",
            value=f"Taxa padrão atual: **{cfg.get('laundry_rate', 25)}%**",
            inline=False
        )

    e.add_field(
        name="🖼️ URL na Embed",
        value=f"Imagem opcional exibida no painel público.\n**URL atual:** {cfg['embed_url'] or 'Nenhuma URL configurada.'}",
        inline=False
    )
    return e

class SystemSelector(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=meta["label"],
                value=key,
                emoji=meta["emoji"],
                description=meta["description"][:90]
            )
            for key, meta in SYSTEMS.items()
        ]
        super().__init__(
            placeholder="Selecione um sistema para gerenciar...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await deny(interaction)
        system = self.values[0]
        await interaction.response.edit_message(
            embed=system_embed(interaction.guild, system),
            view=SystemConfigView(system)
        )

class HomeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=600)
        self.add_item(SystemSelector())

class AccessRoleSelect(discord.ui.RoleSelect):
    def __init__(self, system):
        self.system = system
        super().__init__(
            placeholder="Selecione até 5 cargos de acesso",
            min_values=0,
            max_values=5
        )
    async def callback(self, interaction):
        ids = [r.id for r in self.values]
        update_config(interaction.guild.id, self.system, access_role_ids=ids)
        await interaction.response.edit_message(
            embed=system_embed(interaction.guild, self.system),
            view=SystemConfigView(self.system)
        )

class ApproverRoleSelect(discord.ui.RoleSelect):
    def __init__(self, system):
        self.system = system
        super().__init__(
            placeholder="Selecione até 5 cargos aprovadores",
            min_values=0,
            max_values=5
        )
    async def callback(self, interaction):
        ids = [r.id for r in self.values]
        update_config(interaction.guild.id, self.system, approver_role_ids=ids)
        await interaction.response.edit_message(
            embed=system_embed(interaction.guild, self.system),
            view=SystemConfigView(self.system)
        )

class LogChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, system):
        self.system = system
        super().__init__(
            placeholder="Selecione o canal de logs",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
    async def callback(self, interaction):
        update_config(interaction.guild.id, self.system, log_channel_id=self.values[0].id)
        await interaction.response.edit_message(
            embed=system_embed(interaction.guild, self.system),
            view=SystemConfigView(self.system)
        )

class SingleRoleSelect(discord.ui.RoleSelect):
    def __init__(self, system, field, placeholder):
        self.system = system
        self.field = field
        super().__init__(placeholder=placeholder, min_values=1, max_values=1)
    async def callback(self, interaction):
        update_config(interaction.guild.id, self.system, **{self.field: self.values[0].id})
        await interaction.response.edit_message(
            embed=system_embed(interaction.guild, self.system),
            view=SystemConfigView(self.system)
        )

class URLModal(discord.ui.Modal, title="Configurar URL da Embed"):
    url = discord.ui.TextInput(
        label="URL da imagem",
        placeholder="https://...",
        required=False,
        max_length=500
    )
    def __init__(self, system):
        super().__init__()
        self.system = system
    async def on_submit(self, interaction):
        update_config(interaction.guild.id, self.system, embed_url=str(self.url).strip())
        await interaction.response.send_message("✅ URL atualizada.", ephemeral=True)

class NamePatternModal(discord.ui.Modal, title="Configurar Padrão de Nome"):
    pattern = discord.ui.TextInput(
        label="Padrão",
        placeholder="{id} | {nome}",
        max_length=50
    )
    async def on_submit(self, interaction):
        value = str(self.pattern).strip()
        if "{nome}" not in value:
            return await interaction.response.send_message(
                "❌ O padrão precisa conter `{nome}`.", ephemeral=True
            )
        update_config(interaction.guild.id, "registro", name_pattern=value)
        await interaction.response.send_message("✅ Padrão de nome atualizado.", ephemeral=True)

class LaundryRateModal(discord.ui.Modal, title="Taxa de Lavagem"):
    rate = discord.ui.TextInput(label="Taxa (%)", placeholder="25", max_length=8)
    async def on_submit(self, interaction):
        try:
            rate = float(str(self.rate).replace(",", "."))
            if rate < 0 or rate > 100:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Taxa inválida.", ephemeral=True)
        update_config(interaction.guild.id, "lavagem", laundry_rate=rate)
        await interaction.response.send_message("✅ Taxa atualizada.", ephemeral=True)

class PartnerDiscountModal(discord.ui.Modal, title="Desconto de Parceria"):
    discount = discord.ui.TextInput(label="Desconto (%)", placeholder="10", max_length=8)
    async def on_submit(self, interaction):
        try:
            rate = float(str(self.discount).replace(",", "."))
            if rate < 0 or rate > 100:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Desconto inválido.", ephemeral=True)
        update_config(interaction.guild.id, "vendas", partner_discount=rate)
        await interaction.response.send_message("✅ Desconto atualizado.", ephemeral=True)

class ProductModal(discord.ui.Modal, title="Adicionar Produto"):
    name = discord.ui.TextInput(label="Nome do produto", placeholder="Ex: AK 47", max_length=80)
    price = discord.ui.TextInput(label="Preço unitário", placeholder="Ex: 90000", max_length=20)
    async def on_submit(self, interaction):
        try:
            price = parse_money(self.price)
            if price < 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Preço inválido.", ephemeral=True)
        cfg = get_config(interaction.guild.id, "vendas")
        products = list(cfg.get("products", []))
        products = [p for p in products if p.get("name","").lower() != str(self.name).lower()]
        products.append({"name": str(self.name), "price": price})
        update_config(interaction.guild.id, "vendas", products=products)
        await interaction.response.send_message(
            f"✅ Produto **{self.name}** adicionado por {money(price)}.", ephemeral=True
        )

class SystemConfigView(discord.ui.View):
    def __init__(self, system):
        super().__init__(timeout=600)
        self.system = system

    @discord.ui.button(label="←", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction, button):
        await interaction.response.edit_message(embed=home_embed(interaction.guild), view=HomeView())

    @discord.ui.button(label="🏠", style=discord.ButtonStyle.secondary, row=0)
    async def home(self, interaction, button):
        await interaction.response.edit_message(embed=home_embed(interaction.guild), view=HomeView())

    @discord.ui.button(label="Ligar/Desligar", emoji="⏻", style=discord.ButtonStyle.success, row=0)
    async def toggle(self, interaction, button):
        cfg = get_config(interaction.guild.id, self.system)
        update_config(interaction.guild.id, self.system, enabled=not cfg["enabled"])
        await interaction.response.edit_message(
            embed=system_embed(interaction.guild, self.system),
            view=SystemConfigView(self.system)
        )

    @discord.ui.button(label="Canal de Logs", emoji="🖥️", style=discord.ButtonStyle.secondary, row=1)
    async def logs(self, interaction, button):
        view = discord.ui.View(timeout=120)
        view.add_item(LogChannelSelect(self.system))
        await interaction.response.send_message("Selecione o canal:", view=view, ephemeral=True)

    @discord.ui.button(label="Cargos de Acesso", emoji="🔐", style=discord.ButtonStyle.secondary, row=1)
    async def access(self, interaction, button):
        view = discord.ui.View(timeout=120)
        view.add_item(AccessRoleSelect(self.system))
        await interaction.response.send_message("Selecione os cargos:", view=view, ephemeral=True)

    @discord.ui.button(label="Aprovadores", emoji="✅", style=discord.ButtonStyle.secondary, row=1)
    async def approvers(self, interaction, button):
        if self.system not in {"registro", "encomendas", "ausencia", "farm"}:
            return await interaction.response.send_message(
                "Este sistema não utiliza aprovação.", ephemeral=True
            )
        view = discord.ui.View(timeout=120)
        view.add_item(ApproverRoleSelect(self.system))
        await interaction.response.send_message("Selecione os cargos aprovadores:", view=view, ephemeral=True)

    @discord.ui.button(label="URL Embed", emoji="🖼️", style=discord.ButtonStyle.secondary, row=2)
    async def url(self, interaction, button):
        await interaction.response.send_modal(URLModal(self.system))

    @discord.ui.button(label="Opções Especiais", emoji="⚙️", style=discord.ButtonStyle.primary, row=2)
    async def special(self, interaction, button):
        view = SpecialOptionsView(self.system)
        await interaction.response.send_message(
            embed=embed(
                f"⚙️ Opções • {SYSTEMS[self.system]['label']}",
                "Ajustes específicos deste sistema."
            ),
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="Enviar Painel", emoji="📨", style=discord.ButtonStyle.primary, row=2)
    async def send_panel(self, interaction, button):
        await interaction.response.send_message(
            "Escolha o canal para receber o painel:",
            view=PanelChannelView(self.system),
            ephemeral=True
        )

class SpecialOptionsView(discord.ui.View):
    def __init__(self, system):
        super().__init__(timeout=180)
        self.system = system

    @discord.ui.button(label="Padrão de Nome", style=discord.ButtonStyle.secondary)
    async def pattern(self, interaction, button):
        if self.system != "registro":
            return await interaction.response.send_message("Disponível apenas em Registro.", ephemeral=True)
        await interaction.response.send_modal(NamePatternModal())

    @discord.ui.button(label="Cargo Aprovado", style=discord.ButtonStyle.secondary)
    async def approved_role(self, interaction, button):
        if self.system != "registro":
            return await interaction.response.send_message("Disponível apenas em Registro.", ephemeral=True)
        view = discord.ui.View(timeout=120)
        view.add_item(SingleRoleSelect("registro", "approved_role_id", "Selecione o cargo pós-aprovação"))
        await interaction.response.send_message("Escolha o cargo:", view=view, ephemeral=True)

    @discord.ui.button(label="Cargo Visitante", style=discord.ButtonStyle.secondary)
    async def visitor_role(self, interaction, button):
        if self.system != "registro":
            return await interaction.response.send_message("Disponível apenas em Registro.", ephemeral=True)
        view = discord.ui.View(timeout=120)
        view.add_item(SingleRoleSelect("registro", "visitor_role_id", "Selecione o cargo visitante"))
        await interaction.response.send_message("Escolha o cargo:", view=view, ephemeral=True)

    @discord.ui.button(label="Ativar Visitante", style=discord.ButtonStyle.success)
    async def visitor_toggle(self, interaction, button):
        if self.system != "registro":
            return await interaction.response.send_message("Disponível apenas em Registro.", ephemeral=True)
        cfg = get_config(interaction.guild.id, "registro")
        update_config(interaction.guild.id, "registro", visitor_enabled=not cfg["visitor_enabled"])
        await interaction.response.send_message("✅ Visitante atualizado.", ephemeral=True)

    @discord.ui.button(label="Adicionar Produto", style=discord.ButtonStyle.secondary)
    async def add_product(self, interaction, button):
        if self.system != "vendas":
            return await interaction.response.send_message("Disponível apenas em Vendas.", ephemeral=True)
        await interaction.response.send_modal(ProductModal())

    @discord.ui.button(label="Desconto Parceria", style=discord.ButtonStyle.secondary)
    async def partner_discount(self, interaction, button):
        if self.system != "vendas":
            return await interaction.response.send_message("Disponível apenas em Vendas.", ephemeral=True)
        await interaction.response.send_modal(PartnerDiscountModal())

    @discord.ui.button(label="Taxa Lavagem", style=discord.ButtonStyle.secondary)
    async def laundry_rate(self, interaction, button):
        if self.system != "lavagem":
            return await interaction.response.send_message("Disponível apenas em Lavagem.", ephemeral=True)
        await interaction.response.send_modal(LaundryRateModal())

class PanelChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, system):
        self.system = system
        super().__init__(
            placeholder="Escolha o canal do painel",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
    async def callback(self, interaction):
        ch = self.values[0]
        await send_public_panel(interaction.guild, ch, self.system)
        await interaction.response.send_message(
            f"✅ Painel de **{SYSTEMS[self.system]['label']}** enviado em {ch.mention}.",
            ephemeral=True
        )

class PanelChannelView(discord.ui.View):
    def __init__(self, system):
        super().__init__(timeout=120)
        self.add_item(PanelChannelSelect(system))

# ============================================================
# PAINÉIS PÚBLICOS
# ============================================================

async def send_public_panel(guild, channel, system):
    meta = SYSTEMS[system]
    cfg = get_config(guild.id, system)
    e = embed(
        meta["public_title"],
        meta["public_description"],
        GOLD,
        cfg.get("embed_url", "")
    )
    e.add_field(
        name="Status",
        value="🟢 Sistema disponível" if cfg["enabled"] else "🔴 Sistema indisponível",
        inline=False
    )

    view_map = {
        "registro": RegistroPanel(),
        "vendas": VendasPanel(),
        "banco": BancoPanel(),
        "lavagem": LavagemPanel(),
        "encomendas": EncomendasPanel(),
        "ausencia": AusenciaPanel(),
        "farm": FarmPanel(),
        "bau": BauPanel(),
        "acoes": AcoesPanel(),
    }
    await channel.send(embed=e, view=view_map[system])

# ============================================================
# REGISTRO
# ============================================================

class RegistroModal(discord.ui.Modal, title="Realizar Registro"):
    nome = discord.ui.TextInput(label="Nome", placeholder="Nome do personagem", max_length=80)
    identificacao = discord.ui.TextInput(label="ID / Passaporte", placeholder="Ex: 123", max_length=30)
    telefone = discord.ui.TextInput(label="Telefone", required=False, max_length=40)
    recrutador = discord.ui.TextInput(label="Recrutador", required=False, max_length=80)

    async def on_submit(self, interaction):
        if not enabled(interaction.guild.id, "registro"):
            return await interaction.response.send_message("❌ Sistema de registro está desligado.", ephemeral=True)

        conn = connect()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO registros(guild_id,user_id,nome,identificacao,telefone,recrutador,status,created_at)
               VALUES(?,?,?,?,?,?,'pendente',?)""",
            (
                interaction.guild.id, interaction.user.id, str(self.nome), str(self.identificacao),
                str(self.telefone), str(self.recrutador), now_iso()
            )
        )
        rid = cur.lastrowid
        conn.commit()
        conn.close()

        e = embed("👤 Novo Registro", "Aguardando aprovação.")
        e.add_field(name="Usuário", value=interaction.user.mention, inline=False)
        e.add_field(name="Nome", value=str(self.nome), inline=True)
        e.add_field(name="ID", value=str(self.identificacao), inline=True)
        e.add_field(name="Telefone", value=str(self.telefone) or "Não informado", inline=True)
        e.add_field(name="Recrutador", value=str(self.recrutador) or "Não informado", inline=True)
        e.set_footer(text=f"REG#{rid} • {FOOTER}")

        cfg = get_config(interaction.guild.id, "registro")
        ch = interaction.guild.get_channel(int(cfg["log_channel_id"])) if cfg.get("log_channel_id") else None
        if ch:
            await ch.send(embed=e, view=ApprovalView("registro", rid, interaction.user.id))

        await interaction.response.send_message("✅ Registro enviado para análise.", ephemeral=True)

class RegistroPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Realizar Registro", emoji="👤", style=discord.ButtonStyle.primary, custom_id="public:registro")
    async def register(self, interaction, button):
        await interaction.response.send_modal(RegistroModal())

    @discord.ui.button(label="Entrar como Visitante", emoji="🧳", style=discord.ButtonStyle.secondary, custom_id="public:visitor")
    async def visitor(self, interaction, button):
        cfg = get_config(interaction.guild.id, "registro")
        if not cfg.get("visitor_enabled") or not cfg.get("visitor_role_id"):
            return await interaction.response.send_message("❌ Sistema de visitante está desativado.", ephemeral=True)
        role = interaction.guild.get_role(int(cfg["visitor_role_id"]))
        if not role:
            return await interaction.response.send_message("❌ Cargo visitante não encontrado.", ephemeral=True)
        try:
            await interaction.user.add_roles(role, reason="Acesso visitante")
            await interaction.response.send_message("✅ Cargo de visitante aplicado.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Não consegui aplicar o cargo. Verifique a hierarquia.", ephemeral=True)

# ============================================================
# APROVAÇÃO GENÉRICA
# ============================================================

class ApprovalView(discord.ui.View):
    def __init__(self, system, record_id, target_id):
        super().__init__(timeout=None)
        self.system = system
        self.record_id = int(record_id)
        self.target_id = int(target_id)

    @discord.ui.button(label="Aprovar", emoji="✅", style=discord.ButtonStyle.success)
    async def approve(self, interaction, button):
        if not can_approve(interaction.user, self.system):
            return await deny(interaction, "❌ Você não é aprovador deste sistema.")

        await self.process(interaction, True)

    @discord.ui.button(label="Reprovar", emoji="❌", style=discord.ButtonStyle.danger)
    async def reject(self, interaction, button):
        if not can_approve(interaction.user, self.system):
            return await deny(interaction, "❌ Você não é aprovador deste sistema.")

        await self.process(interaction, False)

    async def process(self, interaction, approved):
        status = "aprovado" if approved else "reprovado"
        table = {
            "registro": "registros",
            "farm": "farms",
            "ausencia": "ausencias",
            "encomendas": "encomendas"
        }[self.system]

        conn = connect()
        row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (self.record_id,)).fetchone()
        if not row or row["status"] != "pendente":
            conn.close()
            return await interaction.response.send_message("Esta solicitação já foi processada.", ephemeral=True)

        conn.execute(
            f"UPDATE {table} SET status=?, reviewer_id=? WHERE id=?",
            (status, interaction.user.id, self.record_id)
        )
        conn.commit()
        conn.close()

        if self.system == "registro" and approved:
            member = interaction.guild.get_member(self.target_id)
            cfg = get_config(interaction.guild.id, "registro")
            if member:
                role = interaction.guild.get_role(int(cfg["approved_role_id"])) if cfg.get("approved_role_id") else None
                try:
                    if role:
                        await member.add_roles(role, reason="Registro aprovado")
                    pattern = cfg.get("name_pattern", "{id} | {nome}")
                    nick = pattern.replace("{id}", str(row["identificacao"])).replace("{nome}", str(row["nome"]))[:32]
                    await member.edit(nick=nick)
                except discord.Forbidden:
                    pass
            add_points(interaction.guild.id, self.target_id, 5)

        if self.system == "farm" and approved:
            add_points(interaction.guild.id, self.target_id, max(1, int(row["quantidade"]) // 100))

        e = interaction.message.embeds[0] if interaction.message.embeds else embed("Solicitação")
        e.color = GREEN if approved else RED
        e.add_field(
            name="Resultado",
            value=f"{'✅ Aprovado' if approved else '❌ Reprovado'} por {interaction.user.mention}",
            inline=False
        )
        await interaction.response.edit_message(embed=e, view=None)

# ============================================================
# VENDAS
# ============================================================

class ProductSelect(discord.ui.Select):
    def __init__(self, products):
        opts = [
            discord.SelectOption(
                label=p["name"][:100],
                value=str(i),
                description=money(float(p["price"]))[:100],
                emoji="📦"
            )
            for i, p in enumerate(products[:25])
        ]
        super().__init__(placeholder="Qual foi o item comercializado?", options=opts)

class SaleStepView(discord.ui.View):
    def __init__(self, products):
        super().__init__(timeout=180)
        self.products = products
        sel = ProductSelect(products)
        sel.callback = self.product_callback
        self.add_item(sel)

    async def product_callback(self, interaction):
        idx = int(self.children[0].values[0])
        product = self.products[idx]
        await interaction.response.send_modal(SaleModal(product["name"], float(product["price"])))

class SaleModal(discord.ui.Modal, title="Registrar Nova Venda"):
    parceria = discord.ui.TextInput(label="Parceria / Sem Parceria", placeholder="com ou sem", max_length=20)
    quantidade = discord.ui.TextInput(label="Quantidade", placeholder="Ex: 2", max_length=10)

    def __init__(self, product, price):
        super().__init__()
        self.product = product
        self.price = price

    async def on_submit(self, interaction):
        if not enabled(interaction.guild.id, "vendas"):
            return await interaction.response.send_message("❌ Sistema de vendas está desligado.", ephemeral=True)
        if not has_access(interaction.user, "vendas"):
            return await interaction.response.send_message("❌ Você não possui o cargo necessário para registrar vendas.", ephemeral=True)

        try:
            qty = parse_int(self.quantidade)
            if qty <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Quantidade inválida.", ephemeral=True)

        ptxt = str(self.parceria).lower()
        is_partner = "com" in ptxt and "sem" not in ptxt
        cfg = get_config(interaction.guild.id, "vendas")
        price = self.price
        if is_partner:
            price *= (1 - float(cfg.get("partner_discount", 0)) / 100)
        total = price * qty

        conn = connect()
        conn.execute(
            """INSERT INTO vendas(guild_id,user_id,produto,parceria,quantidade,unit_price,total,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (interaction.guild.id, interaction.user.id, self.product, int(is_partner), qty, price, total, now_iso())
        )
        conn.commit()
        conn.close()

        add_points(interaction.guild.id, interaction.user.id, 2)

        await interaction.response.send_message(
            embed=embed(
                "✅ Venda Registrada",
                f"**Produto:** {self.product}\n**Quantidade:** {qty}\n"
                f"**Parceria:** {'Sim' if is_partner else 'Não'}\n**Total:** {money(total)}",
                GREEN
            ),
            ephemeral=True
        )
        await log_event(
            interaction.guild, "vendas", "💵 Nova Venda",
            f"{interaction.user.mention}\n**{self.product}** x {qty}\n**Total:** {money(total)}",
            GREEN
        )

class VendasPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Registrar Venda", emoji="📦", style=discord.ButtonStyle.secondary, custom_id="public:venda")
    async def sale(self, interaction, button):
        cfg = get_config(interaction.guild.id, "vendas")
        products = cfg.get("products", [])
        if not products:
            return await interaction.response.send_message("❌ Nenhum produto cadastrado.", ephemeral=True)
        if not has_access(interaction.user, "vendas"):
            return await interaction.response.send_message("❌ Você não possui o cargo necessário para registrar vendas.", ephemeral=True)
        await interaction.response.send_message(
            "Selecione o produto:",
            view=SaleStepView(products),
            ephemeral=True
        )

# ============================================================
# BANCO
# ============================================================

class BankModal(discord.ui.Modal):
    valor = discord.ui.TextInput(label="Valor", placeholder="Ex: 100000", max_length=20)
    descricao = discord.ui.TextInput(label="Descrição", placeholder="Motivo da movimentação", max_length=200)

    def __init__(self, tipo):
        super().__init__(title=f"{'Depositar' if tipo == 'entrada' else 'Retirar'} no Banco")
        self.tipo = tipo

    async def on_submit(self, interaction):
        if not has_access(interaction.user, "banco"):
            return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
        try:
            val = parse_money(self.valor)
            if val <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Valor inválido.", ephemeral=True)

        conn = connect()
        conn.execute(
            "INSERT INTO banco(guild_id,user_id,tipo,valor,descricao,created_at) VALUES(?,?,?,?,?,?)",
            (interaction.guild.id, interaction.user.id, self.tipo, val, str(self.descricao), now_iso())
        )
        conn.commit()
        conn.close()

        await interaction.response.send_message("✅ Movimentação registrada.", ephemeral=True)
        await log_event(
            interaction.guild, "banco", "🏦 Movimentação Bancária",
            f"{interaction.user.mention}\n**Tipo:** {self.tipo}\n**Valor:** {money(val)}\n**Descrição:** {self.descricao}"
        )

def bank_balance(guild_id):
    conn = connect()
    rows = conn.execute("SELECT tipo,valor FROM banco WHERE guild_id=?", (guild_id,)).fetchall()
    conn.close()
    return sum(float(r["valor"]) if r["tipo"] == "entrada" else -float(r["valor"]) for r in rows)

class BancoPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Depositar", emoji="➕", style=discord.ButtonStyle.success, custom_id="public:bank_in")
    async def deposit(self, interaction, button):
        if not enabled(interaction.guild.id, "banco"):
            return await deny(interaction, "❌ Sistema desligado.")
        await interaction.response.send_modal(BankModal("entrada"))

    @discord.ui.button(label="Retirar", emoji="➖", style=discord.ButtonStyle.danger, custom_id="public:bank_out")
    async def withdraw(self, interaction, button):
        if not enabled(interaction.guild.id, "banco"):
            return await deny(interaction, "❌ Sistema desligado.")
        await interaction.response.send_modal(BankModal("saida"))

    @discord.ui.button(label="Ver Saldo", emoji="💰", style=discord.ButtonStyle.secondary, custom_id="public:bank_balance")
    async def balance(self, interaction, button):
        if not has_access(interaction.user, "banco"):
            return await deny(interaction)
        await interaction.response.send_message(
            embed=embed("🏦 Saldo Atual", f"**{money(bank_balance(interaction.guild.id))}**"),
            ephemeral=True
        )

# ============================================================
# LAVAGEM
# ============================================================

class LaundryModal(discord.ui.Modal, title="Registrar Lavagem"):
    bruto = discord.ui.TextInput(label="Valor bruto", placeholder="Ex: 1000000", max_length=20)

    async def on_submit(self, interaction):
        if not has_access(interaction.user, "lavagem"):
            return await deny(interaction)
        try:
            bruto = parse_money(self.bruto)
            if bruto <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Valor inválido.", ephemeral=True)

        cfg = get_config(interaction.guild.id, "lavagem")
        taxa = float(cfg.get("laundry_rate", 25))
        liquido = bruto * (1 - taxa / 100)

        conn = connect()
        conn.execute(
            "INSERT INTO lavagens(guild_id,user_id,bruto,taxa,liquido,created_at) VALUES(?,?,?,?,?,?)",
            (interaction.guild.id, interaction.user.id, bruto, taxa, liquido, now_iso())
        )
        conn.commit()
        conn.close()

        await interaction.response.send_message(
            embed=embed(
                "✅ Lavagem Registrada",
                f"**Bruto:** {money(bruto)}\n**Taxa:** {taxa:.2f}%\n**Líquido:** {money(liquido)}",
                GREEN
            ),
            ephemeral=True
        )
        await log_event(
            interaction.guild, "lavagem", "💸 Lavagem",
            f"{interaction.user.mention}\nBruto: **{money(bruto)}**\nLíquido: **{money(liquido)}**"
        )

class LavagemPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Registrar Lavagem", emoji="💸", style=discord.ButtonStyle.primary, custom_id="public:laundry")
    async def register(self, interaction, button):
        if not enabled(interaction.guild.id, "lavagem"):
            return await deny(interaction, "❌ Sistema desligado.")
        await interaction.response.send_modal(LaundryModal())

# ============================================================
# ENCOMENDAS
# ============================================================

class OrderModal(discord.ui.Modal, title="Registrar Encomenda"):
    descricao = discord.ui.TextInput(label="Descrição do Pedido", style=discord.TextStyle.paragraph, max_length=800)
    data_hora = discord.ui.TextInput(label="Data e Hora", placeholder="Ex: 12/12/26 20:00", max_length=80)
    destinatario = discord.ui.TextInput(label="Destinatário", placeholder="Quem vai receber a encomenda?", max_length=100)

    def __init__(self, responsavel_id):
        super().__init__()
        self.responsavel_id = responsavel_id

    async def on_submit(self, interaction):
        if not has_access(interaction.user, "encomendas"):
            return await deny(interaction)

        conn = connect()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO encomendas(guild_id,author_id,responsavel_id,descricao,data_hora,destinatario,status,created_at)
               VALUES(?,?,?,?,?,?,'pendente',?)""",
            (
                interaction.guild.id, interaction.user.id, self.responsavel_id, str(self.descricao),
                str(self.data_hora), str(self.destinatario), now_iso()
            )
        )
        oid = cur.lastrowid
        conn.commit()
        conn.close()

        e = embed("📦 Nova Encomenda", "Aguardando aprovação.")
        e.add_field(name="Responsável", value=f"<@{self.responsavel_id}>", inline=False)
        e.add_field(name="Pedido", value=str(self.descricao), inline=False)
        e.add_field(name="Data/Hora", value=str(self.data_hora), inline=True)
        e.add_field(name="Destinatário", value=str(self.destinatario), inline=True)
        e.set_footer(text=f"ENC#{oid} • {FOOTER}")

        cfg = get_config(interaction.guild.id, "encomendas")
        ch = interaction.guild.get_channel(int(cfg["log_channel_id"])) if cfg.get("log_channel_id") else None
        if ch:
            await ch.send(embed=e, view=ApprovalView("encomendas", oid, self.responsavel_id))

        await interaction.response.send_message("✅ Encomenda enviada para análise.", ephemeral=True)

class ResponsibleUserSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="Responsável pelo pedido", min_values=1, max_values=1)
    async def callback(self, interaction):
        await interaction.response.send_modal(OrderModal(self.values[0].id))

class OrderStartView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(ResponsibleUserSelect())

class EncomendasPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Abrir Encomenda", emoji="📦", style=discord.ButtonStyle.secondary, custom_id="public:order")
    async def order(self, interaction, button):
        if not enabled(interaction.guild.id, "encomendas"):
            return await deny(interaction, "❌ Sistema desligado.")
        if not has_access(interaction.user, "encomendas"):
            return await deny(interaction)
        await interaction.response.send_message(
            "Selecione o responsável pelo pedido:",
            view=OrderStartView(),
            ephemeral=True
        )

# ============================================================
# AUSÊNCIA
# ============================================================

class AbsenceModal(discord.ui.Modal, title="Solicitar Ausência"):
    periodo = discord.ui.TextInput(label="Período", placeholder="Ex: 31/08 até 05/09", max_length=80)
    motivo = discord.ui.TextInput(label="Motivo", style=discord.TextStyle.paragraph, max_length=500)

    async def on_submit(self, interaction):
        conn = connect()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO ausencias(guild_id,user_id,periodo,motivo,status,created_at)
               VALUES(?,?,?,?,'pendente',?)""",
            (interaction.guild.id, interaction.user.id, str(self.periodo), str(self.motivo), now_iso())
        )
        aid = cur.lastrowid
        conn.commit()
        conn.close()

        e = embed("⌛ Solicitação de Ausência", "Aguardando aprovação.")
        e.add_field(name="Membro", value=interaction.user.mention, inline=False)
        e.add_field(name="Período", value=str(self.periodo), inline=False)
        e.add_field(name="Motivo", value=str(self.motivo), inline=False)
        e.set_footer(text=f"AUS#{aid} • {FOOTER}")

        cfg = get_config(interaction.guild.id, "ausencia")
        ch = interaction.guild.get_channel(int(cfg["log_channel_id"])) if cfg.get("log_channel_id") else None
        if ch:
            await ch.send(embed=e, view=ApprovalView("ausencia", aid, interaction.user.id))

        await interaction.response.send_message("✅ Solicitação enviada.", ephemeral=True)

class AusenciaPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Solicitar Ausência", emoji="⌛", style=discord.ButtonStyle.secondary, custom_id="public:absence")
    async def absence(self, interaction, button):
        if not enabled(interaction.guild.id, "ausencia"):
            return await deny(interaction, "❌ Sistema desligado.")
        await interaction.response.send_modal(AbsenceModal())

# ============================================================
# FARM
# ============================================================

class FarmModal(discord.ui.Modal, title="Registrar Farm"):
    item = discord.ui.TextInput(label="Item", placeholder="Ex: Munição", max_length=80)
    quantidade = discord.ui.TextInput(label="Quantidade", placeholder="Ex: 500", max_length=12)
    comprovante = discord.ui.TextInput(label="Comprovante / Link", required=False, max_length=500)

    async def on_submit(self, interaction):
        try:
            qty = parse_int(self.quantidade)
            if qty <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Quantidade inválida.", ephemeral=True)

        conn = connect()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO farms(guild_id,user_id,item,quantidade,comprovante,status,created_at)
               VALUES(?,?,?,?,?,'pendente',?)""",
            (interaction.guild.id, interaction.user.id, str(self.item), qty, str(self.comprovante), now_iso())
        )
        fid = cur.lastrowid
        conn.commit()
        conn.close()

        e = embed("📦 Novo Farm", "Aguardando aprovação.")
        e.add_field(name="Membro", value=interaction.user.mention, inline=False)
        e.add_field(name="Item", value=str(self.item), inline=True)
        e.add_field(name="Quantidade", value=str(qty), inline=True)
        e.add_field(name="Comprovante", value=str(self.comprovante) or "Não informado", inline=False)
        e.set_footer(text=f"FARM#{fid} • {FOOTER}")

        cfg = get_config(interaction.guild.id, "farm")
        ch = interaction.guild.get_channel(int(cfg["log_channel_id"])) if cfg.get("log_channel_id") else None
        if ch:
            await ch.send(embed=e, view=ApprovalView("farm", fid, interaction.user.id))

        await interaction.response.send_message("✅ Farm enviado.", ephemeral=True)

class FarmPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Registrar Farm", emoji="📦", style=discord.ButtonStyle.success, custom_id="public:farm")
    async def farm(self, interaction, button):
        if not enabled(interaction.guild.id, "farm"):
            return await deny(interaction, "❌ Sistema desligado.")
        await interaction.response.send_modal(FarmModal())

    @discord.ui.button(label="Ranking", emoji="🏆", style=discord.ButtonStyle.secondary, custom_id="public:farm_rank")
    async def rank(self, interaction, button):
        conn = connect()
        rows = conn.execute(
            """SELECT user_id,SUM(quantidade) total FROM farms
               WHERE guild_id=? AND status='aprovado'
               GROUP BY user_id ORDER BY total DESC LIMIT 10""",
            (interaction.guild.id,)
        ).fetchall()
        conn.close()
        lines = [f"**{i+1}.** <@{r['user_id']}> — **{r['total']}**" for i, r in enumerate(rows)]
        await interaction.response.send_message(
            embed=embed("🏆 Ranking de Farm", "\n".join(lines) or "Sem farms aprovados."),
            ephemeral=True
        )

# ============================================================
# BAÚ
# ============================================================

class StockModal(discord.ui.Modal):
    item = discord.ui.TextInput(label="Item", max_length=80)
    quantidade = discord.ui.TextInput(label="Quantidade", max_length=12)

    def __init__(self, bau, tipo):
        super().__init__(title=f"{tipo.title()} • Baú {bau.title()}")
        self.bau = bau
        self.tipo = tipo

    async def on_submit(self, interaction):
        if not has_access(interaction.user, "bau"):
            return await deny(interaction)
        try:
            qty = parse_int(self.quantidade)
            if qty <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Quantidade inválida.", ephemeral=True)

        conn = connect()
        row = conn.execute(
            "SELECT quantidade FROM estoque WHERE guild_id=? AND bau=? AND item=?",
            (interaction.guild.id, self.bau, str(self.item))
        ).fetchone()
        current = int(row["quantidade"]) if row else 0
        delta = qty if self.tipo == "entrada" else -qty

        if current + delta < 0:
            conn.close()
            return await interaction.response.send_message(
                f"❌ Estoque insuficiente. Atual: **{current}**.", ephemeral=True
            )

        conn.execute(
            """INSERT INTO estoque(guild_id,bau,item,quantidade) VALUES(?,?,?,?)
               ON CONFLICT(guild_id,bau,item) DO UPDATE SET quantidade=quantidade+excluded.quantidade""",
            (interaction.guild.id, self.bau, str(self.item), delta)
        )
        conn.execute(
            "INSERT INTO estoque_mov(guild_id,user_id,bau,tipo,item,quantidade,created_at) VALUES(?,?,?,?,?,?,?)",
            (interaction.guild.id, interaction.user.id, self.bau, self.tipo, str(self.item), qty, now_iso())
        )
        conn.commit()
        conn.close()

        await interaction.response.send_message("✅ Estoque atualizado.", ephemeral=True)
        await log_event(
            interaction.guild, "bau", "🧰 Movimento de Baú",
            f"{interaction.user.mention}\n**Baú:** {self.bau}\n**Tipo:** {self.tipo}\n**Item:** {self.item}\n**Qtd:** {qty}"
        )

class BauPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrada Geral", style=discord.ButtonStyle.success, custom_id="public:stock_g_in")
    async def gin(self, interaction, button):
        await interaction.response.send_modal(StockModal("geral", "entrada"))

    @discord.ui.button(label="Retirada Geral", style=discord.ButtonStyle.danger, custom_id="public:stock_g_out")
    async def gout(self, interaction, button):
        await interaction.response.send_modal(StockModal("geral", "retirada"))

    @discord.ui.button(label="Entrada Líder", style=discord.ButtonStyle.success, custom_id="public:stock_l_in")
    async def lin(self, interaction, button):
        await interaction.response.send_modal(StockModal("lider", "entrada"))

    @discord.ui.button(label="Retirada Líder", style=discord.ButtonStyle.danger, custom_id="public:stock_l_out")
    async def lout(self, interaction, button):
        await interaction.response.send_modal(StockModal("lider", "retirada"))

    @discord.ui.button(label="Ver Estoque", emoji="📦", style=discord.ButtonStyle.secondary, custom_id="public:stock_show")
    async def show(self, interaction, button):
        if not has_access(interaction.user, "bau"):
            return await deny(interaction)
        conn = connect()
        rows = conn.execute(
            "SELECT bau,item,quantidade FROM estoque WHERE guild_id=? ORDER BY bau,item",
            (interaction.guild.id,)
        ).fetchall()
        conn.close()
        lines = [f"`{r['bau'].upper():5}` **{r['item']}** — {r['quantidade']}" for r in rows[:40]]
        await interaction.response.send_message(
            embed=embed("🧰 Estoque Atual", "\n".join(lines) or "Estoque vazio."),
            ephemeral=True
        )

# ============================================================
# AÇÕES
# ============================================================

class ActionModal(discord.ui.Modal, title="Registrar Ação"):
    titulo = discord.ui.TextInput(label="Nome da ação", max_length=100)
    horario = discord.ui.TextInput(label="Data / Horário", max_length=80)
    descricao = discord.ui.TextInput(label="Descrição", style=discord.TextStyle.paragraph, max_length=700)

    async def on_submit(self, interaction):
        await log_event(
            interaction.guild, "acoes", f"🎯 {self.titulo}",
            f"**Horário:** {self.horario}\n**Responsável:** {interaction.user.mention}\n\n{self.descricao}",
            RED
        )
        await interaction.response.send_message("✅ Ação registrada.", ephemeral=True)

class AcoesPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Registrar Ação", emoji="🎯", style=discord.ButtonStyle.danger, custom_id="public:action")
    async def action(self, interaction, button):
        if not enabled(interaction.guild.id, "acoes"):
            return await deny(interaction, "❌ Sistema desligado.")
        if not has_access(interaction.user, "acoes"):
            return await deny(interaction)
        await interaction.response.send_modal(ActionModal())

# ============================================================
# MODERAÇÃO / HIERARQUIA / RANKING
# ============================================================

@app_commands.command(name="advertir", description="Aplica advertência em um membro")
async def advertir(interaction: discord.Interaction, membro: discord.Member, motivo: str, pontos: app_commands.Range[int,1,5] = 1):
    if not is_admin(interaction.user):
        return await deny(interaction)
    conn = connect()
    conn.execute(
        "INSERT INTO advertencias(guild_id,user_id,moderator_id,motivo,pontos,created_at) VALUES(?,?,?,?,?,?)",
        (interaction.guild.id, membro.id, interaction.user.id, motivo, pontos, now_iso())
    )
    conn.commit()
    conn.close()
    await interaction.response.send_message(
        embed=embed(
            "⚠️ Advertência",
            f"{membro.mention}\n**Motivo:** {motivo}\n**Pontos:** {pontos}\n**Responsável:** {interaction.user.mention}",
            RED
        )
    )

@app_commands.command(name="promover", description="Adiciona um cargo a um membro")
async def promover(interaction: discord.Interaction, membro: discord.Member, cargo: discord.Role):
    if not is_admin(interaction.user):
        return await deny(interaction)
    if cargo >= interaction.guild.me.top_role:
        return await deny(interaction, "❌ Esse cargo está acima do cargo do bot.")
    await membro.add_roles(cargo, reason=f"Promoção por {interaction.user}")
    add_points(interaction.guild.id, membro.id, 5)
    await interaction.response.send_message(f"✅ {membro.mention} recebeu {cargo.mention}.")

@app_commands.command(name="rebaixar", description="Remove um cargo de um membro")
async def rebaixar(interaction: discord.Interaction, membro: discord.Member, cargo: discord.Role):
    if not is_admin(interaction.user):
        return await deny(interaction)
    await membro.remove_roles(cargo, reason=f"Rebaixamento por {interaction.user}")
    await interaction.response.send_message(f"✅ {cargo.mention} removido de {membro.mention}.")

@app_commands.command(name="ranking", description="Mostra o ranking geral")
async def ranking(interaction: discord.Interaction):
    conn = connect()
    rows = conn.execute(
        "SELECT user_id,pontos FROM pontos WHERE guild_id=? ORDER BY pontos DESC LIMIT 15",
        (interaction.guild.id,)
    ).fetchall()
    conn.close()
    lines = [f"**{i+1}.** <@{r['user_id']}> — **{r['pontos']} pts**" for i, r in enumerate(rows)]
    await interaction.response.send_message(embed=embed("🏆 Ranking Geral", "\n".join(lines) or "Sem pontuação."))

# ============================================================
# PDF DE FARM (SEM DEPENDÊNCIA EXTERNA)
# ============================================================

def pdf_escape(s):
    return str(s).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

def simple_pdf(title, lines):
    page_chunks = [lines[i:i+40] for i in range(0, len(lines), 40)] or [["Sem dados."]]
    objs = []
    objs.append("<< /Type /Catalog /Pages 2 0 R >>")
    page_nums = []
    content_nums = []
    n = 4
    for _ in page_chunks:
        page_nums.append(n)
        content_nums.append(n+1)
        n += 2
    objs.append(f"<< /Type /Pages /Kids [{' '.join(f'{x} 0 R' for x in page_nums)}] /Count {len(page_nums)} >>")
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, chunk in enumerate(page_chunks):
        commands = ["BT", "/F1 15 Tf", "40 800 Td", f"({pdf_escape(title)}) Tj", "0 -26 Td", "/F1 9 Tf"]
        for line in chunk:
            clean = str(line).encode("latin-1", "replace").decode("latin-1")[:120]
            commands += [f"({pdf_escape(clean)}) Tj", "0 -16 Td"]
        commands.append("ET")
        stream = "\n".join(commands)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_nums[i]} 0 R >>")
        objs.append(f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream")
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f"{idx} 0 obj\n{obj}\nendobj\n".encode("latin-1", "replace"))
    xref = out.tell()
    out.write(f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    out.seek(0)
    return out

@app_commands.command(name="relatorio-farm", description="Gera relatório PDF do farm")
async def relatorio_farm(interaction: discord.Interaction):
    if not is_admin(interaction.user) and not can_approve(interaction.user, "farm"):
        return await deny(interaction)
    await interaction.response.defer(ephemeral=True)
    conn = connect()
    rows = conn.execute(
        "SELECT user_id,item,quantidade,status,created_at FROM farms WHERE guild_id=? ORDER BY id DESC LIMIT 500",
        (interaction.guild.id,)
    ).fetchall()
    conn.close()
    lines = [
        f"{r['created_at'][:10]} | {r['user_id']} | {r['item']} | {r['quantidade']} | {r['status']}"
        for r in rows
    ]
    await interaction.followup.send(
        file=discord.File(simple_pdf(f"Relatorio de Farm - {FAC_NAME}", lines), filename="relatorio_farm.pdf"),
        ephemeral=True
    )

# ============================================================
# BACKUP
# ============================================================

async def create_backup(guild):
    data = {
        "name": guild.name,
        "created_at": now_iso(),
        "roles": [
            {"name": r.name, "permissions": r.permissions.value, "color": r.color.value}
            for r in guild.roles if not r.is_default() and not r.managed
        ],
        "categories": [{"name": c.name} for c in guild.categories],
        "channels": [
            {
                "name": ch.name,
                "type": "text" if isinstance(ch, discord.TextChannel) else "voice" if isinstance(ch, discord.VoiceChannel) else "other",
                "category": ch.category.name if ch.category else None
            }
            for ch in guild.channels if not isinstance(ch, discord.CategoryChannel)
        ],
        "configs": {key: get_config(guild.id, key) for key in SYSTEMS}
    }
    path = BACKUP_DIR / f"{guild.id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

@app_commands.command(name="backup", description="Cria backup da estrutura e configurações")
async def backup_cmd(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await deny(interaction)
    await interaction.response.defer(ephemeral=True)
    path = await create_backup(interaction.guild)
    await interaction.followup.send(file=discord.File(path), ephemeral=True)

@tasks.loop(hours=6)
async def backup_loop():
    for guild in bot.guilds:
        try:
            await create_backup(guild)
        except Exception:
            traceback.print_exc()

@backup_loop.before_loop
async def before_backup():
    await bot.wait_until_ready()

# ============================================================
# LOGS / SEGURANÇA
# ============================================================

spam = defaultdict(lambda: deque(maxlen=8))
joins = defaultdict(lambda: deque(maxlen=15))

@bot.event
async def on_message(message):
    if not message.guild or message.author.bot:
        return
    q = spam[(message.guild.id, message.author.id)]
    q.append(time.monotonic())
    if len(q) >= 6 and q[-1] - q[-6] <= 5:
        try:
            await message.author.timeout(
                discord.utils.utcnow() + timedelta(seconds=45),
                reason="Anti-spam"
            )
        except Exception:
            pass
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    q = joins[member.guild.id]
    q.append(time.monotonic())
    # Anti-raid conservador: apenas registra; não bloqueia o servidor automaticamente.
    if len(q) >= 10 and q[-1] - q[-10] <= 15:
        for key in SYSTEMS:
            await log_event(
                member.guild, key, "🚨 Possível Raid Detectada",
                "10 ou mais membros entraram em aproximadamente 15 segundos.",
                RED
            )
            break

@bot.event
async def on_message_delete(message):
    if not message.guild or message.author.bot:
        return
    # Usa primeiro canal de log configurado encontrado.
    for key in SYSTEMS:
        cfg = get_config(message.guild.id, key)
        if cfg.get("log_channel_id"):
            await log_event(
                message.guild, key, "🗑️ Mensagem Apagada",
                f"**Autor:** {message.author.mention}\n**Canal:** {message.channel.mention}\n"
                f"**Conteúdo:** {(message.content or 'Sem texto')[:1200]}",
                RED
            )
            break

# ============================================================
# COMANDOS PRINCIPAIS
# ============================================================

@bot.tree.command(name="gerenciar", description="Abre o painel de gerenciamento do Bot Facção")
@app_commands.default_permissions(administrator=True)
async def gerenciar(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await deny(interaction)
    await interaction.response.send_message(
        embed=home_embed(interaction.guild),
        view=HomeView(),
        ephemeral=True
    )

@bot.tree.command(name="painel", description="Envia o painel público de um sistema")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(sistema=[
    app_commands.Choice(name=meta["label"], value=key)
    for key, meta in SYSTEMS.items()
])
async def painel(interaction: discord.Interaction, sistema: app_commands.Choice[str], canal: discord.TextChannel):
    if not is_admin(interaction.user):
        return await deny(interaction)
    await send_public_panel(interaction.guild, canal, sistema.value)
    await interaction.response.send_message(
        f"✅ Painel de **{SYSTEMS[sistema.value]['label']}** enviado em {canal.mention}.",
        ephemeral=True
    )

@bot.tree.command(name="status-bot", description="Altera o status do bot")
@app_commands.default_permissions(administrator=True)
async def status_bot(interaction: discord.Interaction, texto: str):
    if not is_admin(interaction.user):
        return await deny(interaction)
    await bot.change_presence(activity=discord.Game(name=texto))
    await interaction.response.send_message("✅ Status atualizado.", ephemeral=True)

@bot.tree.command(name="limpar", description="Limpa mensagens")
async def limpar(interaction: discord.Interaction, quantidade: app_commands.Range[int,1,100] = 20):
    if not interaction.user.guild_permissions.manage_messages:
        return await deny(interaction)
    await interaction.response.defer(ephemeral=True)
    msgs = await interaction.channel.purge(limit=quantidade)
    await interaction.followup.send(f"✅ {len(msgs)} mensagens removidas.", ephemeral=True)

@bot.tree.command(name="anuncio-privado", description="Envia anúncio por DM para membros de um cargo")
async def anuncio_privado(interaction: discord.Interaction, cargo: discord.Role, titulo: str, mensagem: str):
    if not is_admin(interaction.user):
        return await deny(interaction)
    await interaction.response.defer(ephemeral=True)
    sent = 0
    failed = 0
    e = embed(titulo, mensagem)
    for member in cargo.members:
        if member.bot:
            continue
        try:
            await member.send(embed=e)
            sent += 1
            await asyncio.sleep(0.35)
        except Exception:
            failed += 1
    await interaction.followup.send(f"✅ Enviados: {sent}\n❌ Falhas: {failed}", ephemeral=True)

# Registra comandos que foram criados com @app_commands.command
bot.tree.add_command(advertir)
bot.tree.add_command(promover)
bot.tree.add_command(rebaixar)
bot.tree.add_command(ranking)
bot.tree.add_command(relatorio_farm)
bot.tree.add_command(backup_cmd)

# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():
    try:
        init_db()

        # Views persistentes dos painéis públicos
        bot.add_view(RegistroPanel())
        bot.add_view(VendasPanel())
        bot.add_view(BancoPanel())
        bot.add_view(LavagemPanel())
        bot.add_view(EncomendasPanel())
        bot.add_view(AusenciaPanel())
        bot.add_view(FarmPanel())
        bot.add_view(BauPanel())
        bot.add_view(AcoesPanel())

        if GUILD_ID.isdigit():
            guild_obj = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild_obj)
            await bot.tree.sync(guild=guild_obj)
        else:
            await bot.tree.sync()

        if not backup_loop.is_running():
            backup_loop.start()

        await bot.change_presence(activity=discord.Game(name=f"Gerenciando {FAC_NAME}"))
        print(f"✅ Online como {bot.user}")

    except Exception:
        traceback.print_exc()

bot.run(TOKEN)

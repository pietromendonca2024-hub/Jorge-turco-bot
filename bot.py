import os
import io
import json
import time
import sqlite3
import asyncio
import traceback
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv


# ============================================================
# BOT FACÇÃO PRO — V3
# Painéis + botões + selects + modais, inspirado na referência
# enviada pelo usuário.
# ============================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

if not TOKEN:
    raise RuntimeError("Configure DISCORD_TOKEN no Railway ou no arquivo .env")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

DB_PATH = os.getenv("DB_PATH", "faccao.db")
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "backups"))
BACKUP_DIR.mkdir(exist_ok=True)

COLOR = 0xD6A323
COLOR_GREEN = 0x57F287
COLOR_RED = 0xED4245
COLOR_BLUE = 0x5865F2
COLOR_DARK = 0x2B2D31

FAC_NAME = os.getenv("FAC_NAME", "JORGE TURCO")
BOT_FOOTER = f"{FAC_NAME} • Sistema de Gerenciamento"

ROLE_DEFS = [
    ("👑 Dono", discord.Permissions(administrator=True)),
    ("👑 Sub-Dono", discord.Permissions(
        manage_guild=True, manage_channels=True, manage_roles=True,
        kick_members=True, ban_members=True, moderate_members=True,
        manage_messages=True
    )),
    ("⚜️ Gerente", discord.Permissions(
        manage_channels=True, manage_messages=True,
        moderate_members=True, kick_members=True
    )),
    ("🔱 Líder", discord.Permissions(
        manage_messages=True, moderate_members=True
    )),
    ("🛡️ Sub-Líder", discord.Permissions(manage_messages=True)),
    ("💼 Gerente de Farm", discord.Permissions(manage_messages=True)),
    ("🎯 Gerente de Ação", discord.Permissions(manage_messages=True)),
    ("🔴 Membro", discord.Permissions()),
    ("🆕 Recruta", discord.Permissions()),
    ("💤 Ausente", discord.Permissions()),
    ("🤝 Parceiro", discord.Permissions()),
    ("👤 Visitante", discord.Permissions()),
]

LEADERSHIP = {"👑 Dono", "👑 Sub-Dono", "⚜️ Gerente", "🔱 Líder", "🛡️ Sub-Líder"}
FARM_STAFF = LEADERSHIP | {"💼 Gerente de Farm"}
ACTION_STAFF = LEADERSHIP | {"🎯 Gerente de Ação"}

STRUCTURE = {
    "📌・INFORMAÇÕES": [
        ("📜・regras", "text"),
        ("📢・anúncios", "text"),
        ("📋・informações", "text"),
        ("🎭・hierarquia", "text"),
        ("🆘・ajuda", "text"),
    ],
    "📝・REGISTRO": [
        ("📝・registro", "text"),
        ("⏳・registros-pendentes", "text"),
        ("👤・visitantes", "text"),
        ("👋・boas-vindas", "text"),
    ],
    "🏘️・COMUNIDADE": [
        ("💬・chat-geral", "text"),
        ("📸・mídias", "text"),
        ("😂・resenha", "text"),
        ("💡・sugestões", "text"),
    ],
    "📦・FARM": [
        ("📦・farm", "text"),
        ("⏳・aprovação-farm", "text"),
        ("🏆・ranking-farm", "text"),
        ("📊・relatórios-farm", "text"),
    ],
    "💰・GESTÃO": [
        ("📦・baú-geral", "text"),
        ("🔐・baú-líder", "text"),
        ("🏦・banco", "text"),
        ("💵・vendas", "text"),
        ("📋・encomendas", "text"),
        ("💸・lavagem", "text"),
        ("🏆・ranking-membros", "text"),
    ],
    "🎯・AÇÕES": [
        ("📋・ações", "text"),
        ("📅・ações-marcadas", "text"),
        ("📸・resultados", "text"),
    ],
    "💤・AUSÊNCIA": [
        ("📋・ausência", "text"),
        ("⏳・aprovação-ausência", "text"),
    ],
    "👑・LIDERANÇA": [
        ("📊・dashboard", "text"),
        ("👥・gerenciar-membros", "text"),
        ("⚠️・advertências", "text"),
        ("🎨・criador-embeds", "text"),
        ("📢・anúncio-privado", "text"),
        ("💾・backups", "text"),
    ],
    "🛡️・LOGS": [
        ("📑・logs-gerais", "text"),
        ("👥・logs-membros", "text"),
        ("💬・logs-mensagens", "text"),
        ("🔊・logs-voz", "text"),
        ("🎭・logs-cargos", "text"),
        ("💰・logs-financeiro", "text"),
        ("📦・logs-farm", "text"),
        ("🛡️・logs-segurança", "text"),
    ],
    "🔊・CALLS": [
        ("🔊・Geral", "voice"),
        ("🔊・Resenha", "voice"),
        ("🔊・Farm", "voice"),
        ("🎯・Ação 01", "voice"),
        ("🎯・Ação 02", "voice"),
        ("👑・Liderança", "voice"),
        ("💤・AFK", "voice"),
    ],
}


# ============================================================
# BANCO
# ============================================================

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def init_db():
    conn = db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            guild_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            PRIMARY KEY (guild_id, key)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            discord_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            passaporte TEXT,
            telefone TEXT,
            recrutador TEXT,
            status TEXT DEFAULT 'pendente',
            aprovado_por INTEGER,
            criado_em TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS advertencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            membro_id INTEGER NOT NULL,
            motivo TEXT NOT NULL,
            pontos INTEGER DEFAULT 1,
            autor_id INTEGER NOT NULL,
            criado_em TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS farms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            membro_id INTEGER NOT NULL,
            item TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            comprovante TEXT,
            status TEXT DEFAULT 'pendente',
            aprovado_por INTEGER,
            criado_em TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS ausencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            membro_id INTEGER NOT NULL,
            motivo TEXT NOT NULL,
            periodo TEXT NOT NULL,
            status TEXT DEFAULT 'pendente',
            aprovado_por INTEGER,
            criado_em TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS estoque (
            guild_id INTEGER NOT NULL,
            bau TEXT NOT NULL,
            item TEXT NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, bau, item)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS estoque_mov (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            bau TEXT NOT NULL,
            item TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            membro_id INTEGER NOT NULL,
            criado_em TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS banco (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            valor REAL NOT NULL,
            descricao TEXT,
            membro_id INTEGER,
            autor_id INTEGER NOT NULL,
            criado_em TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            vendedor_id INTEGER NOT NULL,
            produto TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            valor REAL NOT NULL,
            comprador TEXT,
            criado_em TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS encomendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            cliente TEXT NOT NULL,
            pedido TEXT NOT NULL,
            valor REAL NOT NULL,
            status TEXT DEFAULT 'pendente',
            autor_id INTEGER NOT NULL,
            criado_em TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS lavagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            membro_id INTEGER NOT NULL,
            valor_bruto REAL NOT NULL,
            taxa REAL NOT NULL,
            valor_liquido REAL NOT NULL,
            observacao TEXT,
            criado_em TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS acoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            horario TEXT NOT NULL,
            descricao TEXT,
            responsavel_id INTEGER NOT NULL,
            status TEXT DEFAULT 'marcada',
            criado_em TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS pontos (
            guild_id INTEGER NOT NULL,
            membro_id INTEGER NOT NULL,
            pontos INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, membro_id)
        )
    """)

    conn.commit()
    conn.close()


def setting_get(guild_id: int, key: str, default=None):
    conn = db()
    row = conn.execute(
        "SELECT value FROM settings WHERE guild_id=? AND key=?",
        (guild_id, key)
    ).fetchone()
    conn.close()
    return row["value"] if row else default


def setting_set(guild_id: int, key: str, value):
    conn = db()
    conn.execute(
        "INSERT INTO settings(guild_id,key,value) VALUES(?,?,?) "
        "ON CONFLICT(guild_id,key) DO UPDATE SET value=excluded.value",
        (guild_id, key, str(value))
    )
    conn.commit()
    conn.close()


def add_points(guild_id: int, member_id: int, points: int):
    conn = db()
    conn.execute(
        "INSERT INTO pontos(guild_id,membro_id,pontos) VALUES(?,?,?) "
        "ON CONFLICT(guild_id,membro_id) DO UPDATE SET pontos=pontos+excluded.pontos",
        (guild_id, member_id, points)
    )
    conn.commit()
    conn.close()


# ============================================================
# UTILIDADES
# ============================================================

def brand_embed(title: str, description: str = "", color: int = COLOR):
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text=BOT_FOOTER)
    e.timestamp = datetime.now(timezone.utc)
    return e


def has_any_role(member: discord.Member, names: set[str]):
    return member.guild_permissions.administrator or any(r.name in names for r in member.roles)


def is_staff(member: discord.Member):
    return has_any_role(member, LEADERSHIP)


def is_farm_staff(member: discord.Member):
    return has_any_role(member, FARM_STAFF)


def is_action_staff(member: discord.Member):
    return has_any_role(member, ACTION_STAFF)


def find_role(guild: discord.Guild, name: str):
    return discord.utils.get(guild.roles, name=name)


def find_text(guild: discord.Guild, name: str):
    return discord.utils.get(guild.text_channels, name=name)


async def send_log(guild: discord.Guild, channel_name: str, title: str, description: str, color=COLOR):
    ch = find_text(guild, channel_name)
    if not ch:
        return
    try:
        await ch.send(embed=brand_embed(title, description, color))
    except Exception:
        pass


async def respond_error(interaction: discord.Interaction, text: str):
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


def extract_id_from_footer(message: discord.Message, prefix: str):
    if not message.embeds:
        return None
    footer = message.embeds[0].footer.text or ""
    if footer.startswith(prefix):
        try:
            return int(footer.split("#", 1)[1].split(" ", 1)[0])
        except Exception:
            return None
    return None


async def ensure_role(guild, name, perms):
    role = find_role(guild, name)
    if role:
        return role
    return await guild.create_role(name=name, permissions=perms, reason=f"Setup {FAC_NAME}")


async def ensure_structure(guild: discord.Guild):
    roles = {}
    for name, perms in ROLE_DEFS:
        roles[name] = await ensure_role(guild, name, perms)

    everyone = guild.default_role
    leadership_roles = [roles[n] for n in LEADERSHIP if n in roles]
    member_roles = [roles[n] for n in ("🔴 Membro", "🆕 Recruta") if n in roles]

    for cat_name, channels in STRUCTURE.items():
        category = discord.utils.get(guild.categories, name=cat_name)

        if not category:
            overwrites = None

            if cat_name in {"👑・LIDERANÇA", "🛡️・LOGS"}:
                overwrites = {
                    everyone: discord.PermissionOverwrite(view_channel=False)
                }
                for r in leadership_roles:
                    overwrites[r] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True
                    )

            elif cat_name == "💰・GESTÃO":
                overwrites = {
                    everyone: discord.PermissionOverwrite(view_channel=False)
                }
                for r in leadership_roles:
                    overwrites[r] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True
                    )
                if roles.get("💼 Gerente de Farm"):
                    overwrites[roles["💼 Gerente de Farm"]] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True, read_message_history=True
                    )

            if overwrites:
                category = await guild.create_category(cat_name, overwrites=overwrites, reason=f"Setup {FAC_NAME}")
            else:
                category = await guild.create_category(cat_name, reason=f"Setup {FAC_NAME}")

        for ch_name, ch_type in channels:
            existing = discord.utils.get(category.channels, name=ch_name)
            if existing:
                continue

            if ch_type == "voice":
                await guild.create_voice_channel(ch_name, category=category, reason=f"Setup {FAC_NAME}")
            else:
                await guild.create_text_channel(ch_name, category=category, reason=f"Setup {FAC_NAME}")

    # Permissões especiais de canais
    private_names = {
        "⏳・registros-pendentes": LEADERSHIP,
        "⏳・aprovação-farm": FARM_STAFF,
        "⏳・aprovação-ausência": LEADERSHIP,
        "🔐・baú-líder": LEADERSHIP,
    }

    for ch_name, allowed_names in private_names.items():
        ch = find_text(guild, ch_name)
        if not ch:
            continue

        overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=False)
        }
        for rn in allowed_names:
            role = roles.get(rn)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        try:
            await ch.edit(overwrites=overwrites, reason=f"Permissões {FAC_NAME}")
        except discord.Forbidden:
            pass

    return roles


# ============================================================
# REGISTRO
# ============================================================

class RegistroModal(discord.ui.Modal, title="Registrar Membro"):
    nome = discord.ui.TextInput(
        label="Nome / ID no RP",
        placeholder="Ex: Pietro | 123",
        max_length=80
    )
    passaporte = discord.ui.TextInput(
        label="Passaporte / ID",
        placeholder="Ex: 123",
        max_length=30
    )
    telefone = discord.ui.TextInput(
        label="Telefone",
        placeholder="Ex: 123-456",
        required=False,
        max_length=40
    )
    recrutador = discord.ui.TextInput(
        label="Quem recrutou?",
        placeholder="Nome do recrutador",
        required=False,
        max_length=80
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return await respond_error(interaction, "Use este formulário dentro do servidor.")

        conn = db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO registros
            (guild_id, discord_id, nome, passaporte, telefone, recrutador, status, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, 'pendente', ?)
        """, (
            guild.id, interaction.user.id, str(self.nome), str(self.passaporte),
            str(self.telefone), str(self.recrutador), now_iso()
        ))
        reg_id = cur.lastrowid
        conn.commit()
        conn.close()

        embed = brand_embed(
            "📋 Novo Registro",
            "Um novo membro aguarda aprovação.",
            COLOR
        )
        embed.add_field(name="Membro", value=interaction.user.mention, inline=False)
        embed.add_field(name="Nome / RP", value=str(self.nome), inline=True)
        embed.add_field(name="Passaporte", value=str(self.passaporte), inline=True)
        embed.add_field(name="Telefone", value=str(self.telefone) or "Não informado", inline=True)
        embed.add_field(name="Recrutador", value=str(self.recrutador) or "Não informado", inline=True)
        embed.set_footer(text=f"REG#{reg_id} • {BOT_FOOTER}")

        pending = find_text(guild, "⏳・registros-pendentes")
        if pending:
            await pending.send(embed=embed, view=RegistroApprovalView())

        await interaction.response.send_message(
            embed=brand_embed(
                "✅ Registro enviado",
                "Seu registro foi enviado para a liderança. Aguarde a aprovação.",
                COLOR_GREEN
            ),
            ephemeral=True
        )


class VisitanteModal(discord.ui.Modal, title="Registrar Visitante"):
    nome = discord.ui.TextInput(
        label="Nome do visitante",
        placeholder="Ex: Pietro | Visitante",
        max_length=80
    )
    motivo = discord.ui.TextInput(
        label="Motivo da visita",
        placeholder="Ex: reunião, parceria, recrutamento...",
        max_length=150
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        role = find_role(guild, "👤 Visitante") if guild else None

        if role and isinstance(member, discord.Member):
            try:
                await member.add_roles(role, reason="Registro de visitante")
            except discord.Forbidden:
                pass

        if isinstance(member, discord.Member):
            try:
                await member.edit(nick=str(self.nome)[:32])
            except discord.Forbidden:
                pass

        ch = find_text(guild, "👤・visitantes") if guild else None
        if ch:
            e = brand_embed("👤 Novo Visitante", color=COLOR_BLUE)
            e.add_field(name="Usuário", value=member.mention, inline=False)
            e.add_field(name="Nome", value=str(self.nome), inline=True)
            e.add_field(name="Motivo", value=str(self.motivo), inline=False)
            await ch.send(embed=e)

        await interaction.response.send_message(
            "✅ Visitante registrado e cargo aplicado quando permitido.",
            ephemeral=True
        )


class RegistroApprovalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Aprovar", emoji="✅", style=discord.ButtonStyle.success, custom_id="reg:approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            return await respond_error(interaction, "❌ Apenas a liderança pode aprovar registros.")

        reg_id = extract_id_from_footer(interaction.message, "REG#")
        if not reg_id:
            return await respond_error(interaction, "Não consegui identificar este registro.")

        conn = db()
        row = conn.execute("SELECT * FROM registros WHERE id=?", (reg_id,)).fetchone()
        if not row or row["status"] != "pendente":
            conn.close()
            return await respond_error(interaction, "Este registro já foi processado.")

        conn.execute(
            "UPDATE registros SET status='aprovado', aprovado_por=? WHERE id=?",
            (interaction.user.id, reg_id)
        )
        conn.commit()
        conn.close()

        member = interaction.guild.get_member(row["discord_id"])
        if member:
            member_role = find_role(interaction.guild, "🔴 Membro")
            recruit_role = find_role(interaction.guild, "🆕 Recruta")
            visitor_role = find_role(interaction.guild, "👤 Visitante")

            to_add = [r for r in [member_role] if r]
            to_remove = [r for r in [recruit_role, visitor_role] if r and r in member.roles]

            try:
                if to_add:
                    await member.add_roles(*to_add, reason="Registro aprovado")
                if to_remove:
                    await member.remove_roles(*to_remove, reason="Registro aprovado")
                new_nick = f"{row['nome']} | {row['passaporte']}"[:32]
                await member.edit(nick=new_nick)
            except discord.Forbidden:
                pass

            try:
                await member.send(embed=brand_embed(
                    "✅ Registro aprovado",
                    f"Seu registro em **{interaction.guild.name}** foi aprovado.",
                    COLOR_GREEN
                ))
            except discord.Forbidden:
                pass

        e = interaction.message.embeds[0]
        e.color = COLOR_GREEN
        e.add_field(name="Status", value=f"✅ Aprovado por {interaction.user.mention}", inline=False)
        await interaction.response.edit_message(embed=e, view=None)

        add_points(interaction.guild.id, row["discord_id"], 5)
        await send_log(
            interaction.guild, "👥・logs-membros",
            "✅ Registro aprovado",
            f"<@{row['discord_id']}> foi aprovado por {interaction.user.mention}.",
            COLOR_GREEN
        )

    @discord.ui.button(label="Reprovar", emoji="❌", style=discord.ButtonStyle.danger, custom_id="reg:reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            return await respond_error(interaction, "❌ Apenas a liderança pode reprovar registros.")

        reg_id = extract_id_from_footer(interaction.message, "REG#")
        if not reg_id:
            return await respond_error(interaction, "Não consegui identificar este registro.")

        conn = db()
        row = conn.execute("SELECT * FROM registros WHERE id=?", (reg_id,)).fetchone()
        if not row or row["status"] != "pendente":
            conn.close()
            return await respond_error(interaction, "Este registro já foi processado.")

        conn.execute(
            "UPDATE registros SET status='reprovado', aprovado_por=? WHERE id=?",
            (interaction.user.id, reg_id)
        )
        conn.commit()
        conn.close()

        member = interaction.guild.get_member(row["discord_id"])
        if member:
            try:
                await member.send(embed=brand_embed(
                    "❌ Registro reprovado",
                    f"Seu registro em **{interaction.guild.name}** foi reprovado. Procure a liderança.",
                    COLOR_RED
                ))
            except discord.Forbidden:
                pass

        e = interaction.message.embeds[0]
        e.color = COLOR_RED
        e.add_field(name="Status", value=f"❌ Reprovado por {interaction.user.mention}", inline=False)
        await interaction.response.edit_message(embed=e, view=None)

        await send_log(
            interaction.guild, "👥・logs-membros",
            "❌ Registro reprovado",
            f"<@{row['discord_id']}> foi reprovado por {interaction.user.mention}.",
            COLOR_RED
        )


# ============================================================
# FARM
# ============================================================

class FarmModal(discord.ui.Modal, title="Registrar Farm"):
    item = discord.ui.TextInput(
        label="Item farmado",
        placeholder="Ex: Munição, peças, material...",
        max_length=80
    )
    quantidade = discord.ui.TextInput(
        label="Quantidade",
        placeholder="Ex: 500",
        max_length=10
    )
    comprovante = discord.ui.TextInput(
        label="Comprovante",
        placeholder="Link da imagem ou observação",
        required=False,
        max_length=300
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qtd = int(str(self.quantidade).replace(".", "").replace(",", ""))
            if qtd <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "❌ Informe uma quantidade válida.",
                ephemeral=True
            )

        guild = interaction.guild
        conn = db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO farms
            (guild_id,membro_id,item,quantidade,comprovante,status,criado_em)
            VALUES(?,?,?,?,?,'pendente',?)
        """, (
            guild.id, interaction.user.id, str(self.item), qtd,
            str(self.comprovante), now_iso()
        ))
        farm_id = cur.lastrowid
        conn.commit()
        conn.close()

        e = brand_embed("📦 Farm aguardando aprovação")
        e.add_field(name="Membro", value=interaction.user.mention, inline=False)
        e.add_field(name="Item", value=str(self.item), inline=True)
        e.add_field(name="Quantidade", value=f"{qtd:,}".replace(",", "."), inline=True)
        e.add_field(name="Comprovante", value=str(self.comprovante) or "Não informado", inline=False)
        e.set_footer(text=f"FARM#{farm_id} • {BOT_FOOTER}")

        ch = find_text(guild, "⏳・aprovação-farm")
        if ch:
            await ch.send(embed=e, view=FarmApprovalView())

        await interaction.response.send_message(
            embed=brand_embed("✅ Farm enviado", "Aguarde a aprovação do responsável.", COLOR_GREEN),
            ephemeral=True
        )


class FarmApprovalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Aprovar", emoji="✅", style=discord.ButtonStyle.success, custom_id="farm:approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_farm_staff(interaction.user):
            return await respond_error(interaction, "❌ Você não possui permissão para aprovar farm.")

        farm_id = extract_id_from_footer(interaction.message, "FARM#")
        conn = db()
        row = conn.execute("SELECT * FROM farms WHERE id=?", (farm_id,)).fetchone() if farm_id else None
        if not row or row["status"] != "pendente":
            conn.close()
            return await respond_error(interaction, "Este farm já foi processado.")

        conn.execute(
            "UPDATE farms SET status='aprovado', aprovado_por=? WHERE id=?",
            (interaction.user.id, farm_id)
        )
        conn.commit()
        conn.close()

        add_points(interaction.guild.id, row["membro_id"], max(1, row["quantidade"] // 100))

        e = interaction.message.embeds[0]
        e.color = COLOR_GREEN
        e.add_field(name="Status", value=f"✅ Aprovado por {interaction.user.mention}", inline=False)
        await interaction.response.edit_message(embed=e, view=None)

        await send_log(
            interaction.guild, "📦・logs-farm",
            "✅ Farm aprovado",
            f"<@{row['membro_id']}> • **{row['item']}** • **{row['quantidade']}**\n"
            f"Aprovado por {interaction.user.mention}.",
            COLOR_GREEN
        )
        await update_ranking_farm(interaction.guild)

    @discord.ui.button(label="Reprovar", emoji="❌", style=discord.ButtonStyle.danger, custom_id="farm:reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_farm_staff(interaction.user):
            return await respond_error(interaction, "❌ Você não possui permissão para reprovar farm.")

        farm_id = extract_id_from_footer(interaction.message, "FARM#")
        conn = db()
        row = conn.execute("SELECT * FROM farms WHERE id=?", (farm_id,)).fetchone() if farm_id else None
        if not row or row["status"] != "pendente":
            conn.close()
            return await respond_error(interaction, "Este farm já foi processado.")

        conn.execute(
            "UPDATE farms SET status='reprovado', aprovado_por=? WHERE id=?",
            (interaction.user.id, farm_id)
        )
        conn.commit()
        conn.close()

        e = interaction.message.embeds[0]
        e.color = COLOR_RED
        e.add_field(name="Status", value=f"❌ Reprovado por {interaction.user.mention}", inline=False)
        await interaction.response.edit_message(embed=e, view=None)

        await send_log(
            interaction.guild, "📦・logs-farm",
            "❌ Farm reprovado",
            f"<@{row['membro_id']}> • **{row['item']}** • **{row['quantidade']}**",
            COLOR_RED
        )


async def update_ranking_farm(guild: discord.Guild):
    ch = find_text(guild, "🏆・ranking-farm")
    if not ch:
        return

    conn = db()
    rows = conn.execute("""
        SELECT membro_id, SUM(quantidade) total
        FROM farms
        WHERE guild_id=? AND status='aprovado'
        GROUP BY membro_id
        ORDER BY total DESC
        LIMIT 15
    """, (guild.id,)).fetchall()
    conn.close()

    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows):
        prefix = medals[i] if i < 3 else f"`{i+1:02}`"
        lines.append(f"{prefix} <@{row['membro_id']}> — **{row['total']:,}**".replace(",", "."))

    e = brand_embed(
        "🏆 Ranking de Farm",
        "\n".join(lines) if lines else "Ainda não existem farms aprovados.",
        COLOR
    )

    # Mantém apenas um painel do bot no canal quando possível
    try:
        async for msg in ch.history(limit=30):
            if msg.author == bot.user and msg.embeds and msg.embeds[0].title == "🏆 Ranking de Farm":
                return await msg.edit(embed=e)
        await ch.send(embed=e)
    except discord.Forbidden:
        pass


# ============================================================
# AUSÊNCIA
# ============================================================

class AusenciaModal(discord.ui.Modal, title="Solicitar Ausência"):
    periodo = discord.ui.TextInput(
        label="Período",
        placeholder="Ex: 31/08 até 05/09",
        max_length=80
    )
    motivo = discord.ui.TextInput(
        label="Motivo",
        placeholder="Explique brevemente o motivo",
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        conn = db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ausencias
            (guild_id,membro_id,motivo,periodo,status,criado_em)
            VALUES(?,?,?,?,'pendente',?)
        """, (
            guild.id, interaction.user.id, str(self.motivo),
            str(self.periodo), now_iso()
        ))
        aid = cur.lastrowid
        conn.commit()
        conn.close()

        e = brand_embed("💤 Solicitação de Ausência")
        e.add_field(name="Membro", value=interaction.user.mention, inline=False)
        e.add_field(name="Período", value=str(self.periodo), inline=False)
        e.add_field(name="Motivo", value=str(self.motivo), inline=False)
        e.set_footer(text=f"AUS#{aid} • {BOT_FOOTER}")

        ch = find_text(guild, "⏳・aprovação-ausência")
        if ch:
            await ch.send(embed=e, view=AusenciaApprovalView())

        await interaction.response.send_message(
            "✅ Sua solicitação de ausência foi enviada.",
            ephemeral=True
        )


class AusenciaApprovalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Aprovar", emoji="✅", style=discord.ButtonStyle.success, custom_id="aus:approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            return await respond_error(interaction, "❌ Apenas a liderança pode aprovar.")

        aid = extract_id_from_footer(interaction.message, "AUS#")
        conn = db()
        row = conn.execute("SELECT * FROM ausencias WHERE id=?", (aid,)).fetchone() if aid else None
        if not row or row["status"] != "pendente":
            conn.close()
            return await respond_error(interaction, "Esta solicitação já foi processada.")

        conn.execute(
            "UPDATE ausencias SET status='aprovado', aprovado_por=? WHERE id=?",
            (interaction.user.id, aid)
        )
        conn.commit()
        conn.close()

        member = interaction.guild.get_member(row["membro_id"])
        role = find_role(interaction.guild, "💤 Ausente")
        if member and role:
            try:
                await member.add_roles(role, reason="Ausência aprovada")
            except discord.Forbidden:
                pass

        e = interaction.message.embeds[0]
        e.color = COLOR_GREEN
        e.add_field(name="Status", value=f"✅ Aprovada por {interaction.user.mention}", inline=False)
        await interaction.response.edit_message(embed=e, view=None)

    @discord.ui.button(label="Reprovar", emoji="❌", style=discord.ButtonStyle.danger, custom_id="aus:reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            return await respond_error(interaction, "❌ Apenas a liderança pode reprovar.")

        aid = extract_id_from_footer(interaction.message, "AUS#")
        conn = db()
        row = conn.execute("SELECT * FROM ausencias WHERE id=?", (aid,)).fetchone() if aid else None
        if not row or row["status"] != "pendente":
            conn.close()
            return await respond_error(interaction, "Esta solicitação já foi processada.")

        conn.execute(
            "UPDATE ausencias SET status='reprovado', aprovado_por=? WHERE id=?",
            (interaction.user.id, aid)
        )
        conn.commit()
        conn.close()

        e = interaction.message.embeds[0]
        e.color = COLOR_RED
        e.add_field(name="Status", value=f"❌ Reprovada por {interaction.user.mention}", inline=False)
        await interaction.response.edit_message(embed=e, view=None)


# ============================================================
# GESTÃO ECONÔMICA — MODAIS
# ============================================================

class EstoqueModal(discord.ui.Modal):
    def __init__(self, bau: str, tipo: str):
        self.bau = bau
        self.tipo = tipo
        super().__init__(title=f"{tipo.title()} • {bau.title()}")

        self.item = discord.ui.TextInput(
            label="Item",
            placeholder="Ex: Munição, material, peças...",
            max_length=80
        )
        self.quantidade = discord.ui.TextInput(
            label="Quantidade",
            placeholder="Ex: 100",
            max_length=10
        )
        self.add_item(self.item)
        self.add_item(self.quantidade)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_staff(interaction.user) and self.bau == "lider":
            return await respond_error(interaction, "❌ Baú de líder é exclusivo da liderança.")

        try:
            qtd = int(str(self.quantidade).replace(".", "").replace(",", ""))
            if qtd <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Quantidade inválida.", ephemeral=True)

        delta = qtd if self.tipo == "entrada" else -qtd

        conn = db()
        row = conn.execute(
            "SELECT quantidade FROM estoque WHERE guild_id=? AND bau=? AND item=?",
            (interaction.guild.id, self.bau, str(self.item))
        ).fetchone()
        atual = row["quantidade"] if row else 0

        if atual + delta < 0:
            conn.close()
            return await interaction.response.send_message(
                f"❌ Estoque insuficiente. Atual: **{atual}**.",
                ephemeral=True
            )

        conn.execute(
            "INSERT INTO estoque(guild_id,bau,item,quantidade) VALUES(?,?,?,?) "
            "ON CONFLICT(guild_id,bau,item) DO UPDATE SET quantidade=quantidade+excluded.quantidade",
            (interaction.guild.id, self.bau, str(self.item), delta)
        )
        conn.execute("""
            INSERT INTO estoque_mov
            (guild_id,bau,item,quantidade,tipo,membro_id,criado_em)
            VALUES(?,?,?,?,?,?,?)
        """, (
            interaction.guild.id, self.bau, str(self.item), qtd,
            self.tipo, interaction.user.id, now_iso()
        ))
        conn.commit()
        conn.close()

        await interaction.response.send_message(
            embed=brand_embed(
                "📦 Estoque atualizado",
                f"**Baú:** {self.bau.title()}\n"
                f"**Operação:** {self.tipo.title()}\n"
                f"**Item:** {self.item}\n"
                f"**Quantidade:** {qtd}",
                COLOR_GREEN
            ),
            ephemeral=True
        )

        await send_log(
            interaction.guild, "💰・logs-financeiro",
            "📦 Movimentação de estoque",
            f"{interaction.user.mention} • {self.tipo} • **{self.item}** x **{qtd}** • baú {self.bau}"
        )


class BancoModal(discord.ui.Modal, title="Registrar Movimento no Banco"):
    tipo = discord.ui.TextInput(label="Tipo", placeholder="entrada ou saída", max_length=10)
    valor = discord.ui.TextInput(label="Valor", placeholder="Ex: 250000", max_length=20)
    descricao = discord.ui.TextInput(
        label="Descrição",
        placeholder="Motivo da movimentação",
        max_length=200
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            return await respond_error(interaction, "❌ Apenas a liderança gerencia o banco.")

        tipo = str(self.tipo).strip().lower()
        if tipo not in {"entrada", "saida", "saída"}:
            return await interaction.response.send_message("❌ Use `entrada` ou `saída`.", ephemeral=True)

        try:
            valor = float(str(self.valor).replace(".", "").replace(",", "."))
            if valor <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Valor inválido.", ephemeral=True)

        conn = db()
        conn.execute("""
            INSERT INTO banco
            (guild_id,tipo,valor,descricao,membro_id,autor_id,criado_em)
            VALUES(?,?,?,?,?,?,?)
        """, (
            interaction.guild.id, "saida" if tipo in {"saida", "saída"} else "entrada",
            valor, str(self.descricao), None, interaction.user.id, now_iso()
        ))
        conn.commit()
        conn.close()

        await interaction.response.send_message("✅ Movimento bancário registrado.", ephemeral=True)
        await send_log(
            interaction.guild, "💰・logs-financeiro",
            "🏦 Banco",
            f"{interaction.user.mention} registrou **{tipo}** de **R$ {valor:,.2f}**\n{self.descricao}"
        )


class VendaModal(discord.ui.Modal, title="Registrar Venda"):
    produto = discord.ui.TextInput(label="Produto", placeholder="Ex: Munição", max_length=80)
    quantidade = discord.ui.TextInput(label="Quantidade", placeholder="Ex: 100", max_length=10)
    valor = discord.ui.TextInput(label="Valor total", placeholder="Ex: 50000", max_length=20)
    comprador = discord.ui.TextInput(label="Comprador", required=False, max_length=80)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qtd = int(str(self.quantidade).replace(".", "").replace(",", ""))
            valor = float(str(self.valor).replace(".", "").replace(",", "."))
            if qtd <= 0 or valor <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Quantidade ou valor inválido.", ephemeral=True)

        conn = db()
        conn.execute("""
            INSERT INTO vendas
            (guild_id,vendedor_id,produto,quantidade,valor,comprador,criado_em)
            VALUES(?,?,?,?,?,?,?)
        """, (
            interaction.guild.id, interaction.user.id, str(self.produto),
            qtd, valor, str(self.comprador), now_iso()
        ))
        conn.commit()
        conn.close()

        add_points(interaction.guild.id, interaction.user.id, 3)

        await interaction.response.send_message("✅ Venda registrada.", ephemeral=True)
        ch = find_text(interaction.guild, "💵・vendas")
        if ch:
            e = brand_embed("💵 Nova Venda", color=COLOR_GREEN)
            e.add_field(name="Vendedor", value=interaction.user.mention, inline=False)
            e.add_field(name="Produto", value=str(self.produto), inline=True)
            e.add_field(name="Quantidade", value=str(qtd), inline=True)
            e.add_field(name="Valor", value=f"R$ {valor:,.2f}", inline=True)
            e.add_field(name="Comprador", value=str(self.comprador) or "Não informado", inline=True)
            await ch.send(embed=e)


class EncomendaModal(discord.ui.Modal, title="Registrar Encomenda"):
    cliente = discord.ui.TextInput(label="Cliente", placeholder="Nome / ID do cliente", max_length=80)
    pedido = discord.ui.TextInput(
        label="Pedido",
        placeholder="Ex: 500 munições + 2 itens...",
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    valor = discord.ui.TextInput(label="Valor combinado", placeholder="Ex: 150000", max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            valor = float(str(self.valor).replace(".", "").replace(",", "."))
            if valor < 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Valor inválido.", ephemeral=True)

        conn = db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO encomendas
            (guild_id,cliente,pedido,valor,status,autor_id,criado_em)
            VALUES(?,?,?,?,'pendente',?,?)
        """, (
            interaction.guild.id, str(self.cliente), str(self.pedido),
            valor, interaction.user.id, now_iso()
        ))
        eid = cur.lastrowid
        conn.commit()
        conn.close()

        ch = find_text(interaction.guild, "📋・encomendas")
        if ch:
            e = brand_embed("📋 Nova Encomenda")
            e.add_field(name="Cliente", value=str(self.cliente), inline=True)
            e.add_field(name="Valor", value=f"R$ {valor:,.2f}", inline=True)
            e.add_field(name="Pedido", value=str(self.pedido), inline=False)
            e.add_field(name="Responsável", value=interaction.user.mention, inline=False)
            e.set_footer(text=f"ENC#{eid} • {BOT_FOOTER}")
            await ch.send(embed=e)

        await interaction.response.send_message("✅ Encomenda registrada.", ephemeral=True)


class LavagemModal(discord.ui.Modal, title="Registrar Lavagem"):
    valor = discord.ui.TextInput(label="Valor bruto", placeholder="Ex: 1000000", max_length=20)
    taxa = discord.ui.TextInput(label="Taxa (%)", placeholder="Ex: 25", max_length=10)
    observacao = discord.ui.TextInput(
        label="Observação",
        required=False,
        max_length=150
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bruto = float(str(self.valor).replace(".", "").replace(",", "."))
            taxa = float(str(self.taxa).replace(",", "."))
            if bruto <= 0 or taxa < 0 or taxa > 100:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Valor ou taxa inválida.", ephemeral=True)

        liquido = bruto * (1 - taxa / 100)

        conn = db()
        conn.execute("""
            INSERT INTO lavagens
            (guild_id,membro_id,valor_bruto,taxa,valor_liquido,observacao,criado_em)
            VALUES(?,?,?,?,?,?,?)
        """, (
            interaction.guild.id, interaction.user.id, bruto,
            taxa, liquido, str(self.observacao), now_iso()
        ))
        conn.commit()
        conn.close()

        ch = find_text(interaction.guild, "💸・lavagem")
        if ch:
            e = brand_embed("💸 Lavagem Registrada", color=COLOR_GREEN)
            e.add_field(name="Responsável", value=interaction.user.mention, inline=False)
            e.add_field(name="Bruto", value=f"R$ {bruto:,.2f}", inline=True)
            e.add_field(name="Taxa", value=f"{taxa:.2f}%", inline=True)
            e.add_field(name="Líquido", value=f"R$ {liquido:,.2f}", inline=True)
            await ch.send(embed=e)

        await interaction.response.send_message("✅ Lavagem registrada.", ephemeral=True)


class AcaoModal(discord.ui.Modal, title="Marcar Ação"):
    titulo_acao = discord.ui.TextInput(label="Nome da ação", placeholder="Ex: Ação Cayo Perico", max_length=100)
    horario = discord.ui.TextInput(label="Data / Horário", placeholder="Ex: 31/08 às 22:00", max_length=80)
    descricao = discord.ui.TextInput(
        label="Descrição / Ponto de encontro",
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not is_action_staff(interaction.user):
            return await respond_error(interaction, "❌ Você não gerencia ações.")

        conn = db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO acoes
            (guild_id,titulo,horario,descricao,responsavel_id,status,criado_em)
            VALUES(?,?,?,?,?,'marcada',?)
        """, (
            interaction.guild.id, str(self.titulo_acao), str(self.horario),
            str(self.descricao), interaction.user.id, now_iso()
        ))
        aid = cur.lastrowid
        conn.commit()
        conn.close()

        ch = find_text(interaction.guild, "📅・ações-marcadas")
        if ch:
            e = brand_embed(f"🎯 {self.titulo_acao}", color=COLOR_RED)
            e.add_field(name="Horário", value=str(self.horario), inline=False)
            e.add_field(name="Informações", value=str(self.descricao), inline=False)
            e.add_field(name="Responsável", value=interaction.user.mention, inline=False)
            e.set_footer(text=f"ACAO#{aid} • {BOT_FOOTER}")
            await ch.send(content="@everyone", embed=e)

        await interaction.response.send_message("✅ Ação marcada.", ephemeral=True)


# ============================================================
# PAINÉIS
# ============================================================

class MainPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Registro", emoji="📝", style=discord.ButtonStyle.primary, custom_id="panel:registro", row=0)
    async def registro(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegistroModal())

    @discord.ui.button(label="Visitante", emoji="👤", style=discord.ButtonStyle.secondary, custom_id="panel:visitante", row=0)
    async def visitante(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VisitanteModal())

    @discord.ui.button(label="Farm", emoji="📦", style=discord.ButtonStyle.success, custom_id="panel:farm", row=0)
    async def farm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FarmModal())

    @discord.ui.button(label="Ausência", emoji="💤", style=discord.ButtonStyle.secondary, custom_id="panel:ausencia", row=0)
    async def ausencia(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AusenciaModal())

    @discord.ui.button(label="Ranking", emoji="🏆", style=discord.ButtonStyle.secondary, custom_id="panel:ranking", row=1)
    async def ranking(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = db()
        rows = conn.execute("""
            SELECT membro_id,pontos FROM pontos
            WHERE guild_id=?
            ORDER BY pontos DESC LIMIT 10
        """, (interaction.guild.id,)).fetchall()
        conn.close()

        txt = "\n".join(
            f"**{i+1}.** <@{r['membro_id']}> — **{r['pontos']} pts**"
            for i, r in enumerate(rows)
        ) or "Ainda não existem pontos registrados."

        await interaction.response.send_message(
            embed=brand_embed("🏆 Ranking de Membros", txt),
            ephemeral=True
        )

    @discord.ui.button(label="Ajuda", emoji="❓", style=discord.ButtonStyle.secondary, custom_id="panel:help", row=1)
    async def help(self, interaction: discord.Interaction, button: discord.ui.Button):
        e = brand_embed(
            "❓ Central de Ajuda",
            "Use os botões do painel para acessar os sistemas.\n\n"
            "📝 **Registro:** envia seus dados para aprovação.\n"
            "👤 **Visitante:** registra acesso temporário.\n"
            "📦 **Farm:** envia produção para aprovação.\n"
            "💤 **Ausência:** solicita afastamento.\n"
            "🏆 **Ranking:** consulta sua colocação."
        )
        await interaction.response.send_message(embed=e, ephemeral=True)


class ManagementSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Baú Geral • Entrada", value="bau_g_in", emoji="📥"),
            discord.SelectOption(label="Baú Geral • Retirada", value="bau_g_out", emoji="📤"),
            discord.SelectOption(label="Baú Líder • Entrada", value="bau_l_in", emoji="🔐"),
            discord.SelectOption(label="Baú Líder • Retirada", value="bau_l_out", emoji="🔐"),
            discord.SelectOption(label="Banco", value="banco", emoji="🏦"),
            discord.SelectOption(label="Registrar Venda", value="venda", emoji="💵"),
            discord.SelectOption(label="Registrar Encomenda", value="encomenda", emoji="📋"),
            discord.SelectOption(label="Registrar Lavagem", value="lavagem", emoji="💸"),
            discord.SelectOption(label="Marcar Ação", value="acao", emoji="🎯"),
            discord.SelectOption(label="Ver Estoque", value="estoque", emoji="📦"),
        ]
        super().__init__(
            placeholder="Selecione uma função de gerenciamento...",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="dashboard:select"
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            return await respond_error(interaction, "❌ Este painel é exclusivo da liderança.")

        value = self.values[0]

        if value == "bau_g_in":
            return await interaction.response.send_modal(EstoqueModal("geral", "entrada"))
        if value == "bau_g_out":
            return await interaction.response.send_modal(EstoqueModal("geral", "retirada"))
        if value == "bau_l_in":
            return await interaction.response.send_modal(EstoqueModal("lider", "entrada"))
        if value == "bau_l_out":
            return await interaction.response.send_modal(EstoqueModal("lider", "retirada"))
        if value == "banco":
            return await interaction.response.send_modal(BancoModal())
        if value == "venda":
            return await interaction.response.send_modal(VendaModal())
        if value == "encomenda":
            return await interaction.response.send_modal(EncomendaModal())
        if value == "lavagem":
            return await interaction.response.send_modal(LavagemModal())
        if value == "acao":
            return await interaction.response.send_modal(AcaoModal())
        if value == "estoque":
            conn = db()
            rows = conn.execute("""
                SELECT bau,item,quantidade FROM estoque
                WHERE guild_id=? ORDER BY bau,item
            """, (interaction.guild.id,)).fetchall()
            conn.close()

            if rows:
                txt = "\n".join(
                    f"`{r['bau'].upper():5}` • **{r['item']}** — {r['quantidade']}"
                    for r in rows[:40]
                )
            else:
                txt = "O estoque ainda está vazio."

            return await interaction.response.send_message(
                embed=brand_embed("📦 Estoque Atual", txt),
                ephemeral=True
            )


class ManagementPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ManagementSelect())

    @discord.ui.button(label="Atualizar Dashboard", emoji="🔄", style=discord.ButtonStyle.secondary, custom_id="dashboard:refresh", row=1)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            return await respond_error(interaction, "❌ Apenas liderança.")

        e = await build_dashboard_embed(interaction.guild)
        await interaction.response.edit_message(embed=e, view=self)


async def build_dashboard_embed(guild: discord.Guild):
    conn = db()

    reg_pend = conn.execute(
        "SELECT COUNT(*) n FROM registros WHERE guild_id=? AND status='pendente'",
        (guild.id,)
    ).fetchone()["n"]

    farm_pend = conn.execute(
        "SELECT COUNT(*) n FROM farms WHERE guild_id=? AND status='pendente'",
        (guild.id,)
    ).fetchone()["n"]

    aus_pend = conn.execute(
        "SELECT COUNT(*) n FROM ausencias WHERE guild_id=? AND status='pendente'",
        (guild.id,)
    ).fetchone()["n"]

    banco_rows = conn.execute(
        "SELECT tipo,valor FROM banco WHERE guild_id=?",
        (guild.id,)
    ).fetchall()

    total_vendas = conn.execute(
        "SELECT COALESCE(SUM(valor),0) t FROM vendas WHERE guild_id=?",
        (guild.id,)
    ).fetchone()["t"]

    conn.close()

    saldo = 0
    for row in banco_rows:
        saldo += row["valor"] if row["tipo"] == "entrada" else -row["valor"]

    e = brand_embed(
        f"📊 Dashboard • {FAC_NAME}",
        "Central de gerenciamento da organização.\n"
        "Selecione uma função no menu abaixo.",
        COLOR
    )
    e.add_field(name="👥 Membros", value=str(guild.member_count), inline=True)
    e.add_field(name="📝 Registros pendentes", value=str(reg_pend), inline=True)
    e.add_field(name="📦 Farms pendentes", value=str(farm_pend), inline=True)
    e.add_field(name="💤 Ausências pendentes", value=str(aus_pend), inline=True)
    e.add_field(name="🏦 Saldo registrado", value=f"R$ {saldo:,.2f}", inline=True)
    e.add_field(name="💵 Vendas", value=f"R$ {total_vendas:,.2f}", inline=True)
    return e


# ============================================================
# ADVERTÊNCIA / HIERARQUIA
# ============================================================

@app_commands.default_permissions(administrator=True)
@bot.tree.command(name="advertir", description="Aplica uma advertência a um membro")
@app_commands.describe(membro="Membro", motivo="Motivo", pontos="Quantidade de pontos da advertência")
async def advertir(interaction: discord.Interaction, membro: discord.Member, motivo: str, pontos: app_commands.Range[int, 1, 5] = 1):
    if not is_staff(interaction.user):
        return await respond_error(interaction, "❌ Apenas a liderança pode advertir.")

    conn = db()
    conn.execute("""
        INSERT INTO advertencias
        (guild_id,membro_id,motivo,pontos,autor_id,criado_em)
        VALUES(?,?,?,?,?,?)
    """, (
        interaction.guild.id, membro.id, motivo, pontos,
        interaction.user.id, now_iso()
    ))
    conn.commit()
    conn.close()

    e = brand_embed("⚠️ Advertência", color=COLOR_RED)
    e.add_field(name="Membro", value=membro.mention, inline=False)
    e.add_field(name="Motivo", value=motivo, inline=False)
    e.add_field(name="Pontos", value=str(pontos), inline=True)
    e.add_field(name="Aplicada por", value=interaction.user.mention, inline=True)

    ch = find_text(interaction.guild, "⚠️・advertências")
    if ch:
        await ch.send(embed=e)

    try:
        await membro.send(embed=e)
    except discord.Forbidden:
        pass

    await interaction.response.send_message("✅ Advertência registrada.", ephemeral=True)


@bot.tree.command(name="advertencias", description="Consulta advertências de um membro")
async def advertencias(interaction: discord.Interaction, membro: discord.Member):
    conn = db()
    rows = conn.execute("""
        SELECT motivo,pontos,autor_id,criado_em
        FROM advertencias WHERE guild_id=? AND membro_id=?
        ORDER BY id DESC LIMIT 10
    """, (interaction.guild.id, membro.id)).fetchall()
    conn.close()

    if not rows:
        text = "Nenhuma advertência registrada."
    else:
        text = "\n\n".join(
            f"⚠️ **{r['pontos']} ponto(s)** • {r['motivo']}\nPor <@{r['autor_id']}>"
            for r in rows
        )

    await interaction.response.send_message(
        embed=brand_embed(f"⚠️ Advertências • {membro.display_name}", text),
        ephemeral=True
    )


@bot.tree.command(name="promover", description="Adiciona um cargo de hierarquia a um membro")
async def promover(interaction: discord.Interaction, membro: discord.Member, cargo: discord.Role):
    if not is_staff(interaction.user):
        return await respond_error(interaction, "❌ Apenas a liderança pode promover.")

    if cargo >= interaction.guild.me.top_role:
        return await respond_error(interaction, "❌ O cargo selecionado está acima do cargo do bot.")

    await membro.add_roles(cargo, reason=f"Promoção por {interaction.user}")
    add_points(interaction.guild.id, membro.id, 10)

    await interaction.response.send_message(
        embed=brand_embed(
            "⬆️ Promoção",
            f"{membro.mention} foi promovido para {cargo.mention}\nPor {interaction.user.mention}",
            COLOR_GREEN
        )
    )
    await send_log(
        interaction.guild, "🎭・logs-cargos",
        "⬆️ Promoção",
        f"{membro.mention} recebeu {cargo.mention} por {interaction.user.mention}.",
        COLOR_GREEN
    )


@bot.tree.command(name="rebaixar", description="Remove um cargo de hierarquia de um membro")
async def rebaixar(interaction: discord.Interaction, membro: discord.Member, cargo: discord.Role):
    if not is_staff(interaction.user):
        return await respond_error(interaction, "❌ Apenas a liderança pode rebaixar.")

    await membro.remove_roles(cargo, reason=f"Rebaixamento por {interaction.user}")

    await interaction.response.send_message(
        embed=brand_embed(
            "⬇️ Rebaixamento",
            f"{membro.mention} perdeu {cargo.mention}\nPor {interaction.user.mention}",
            COLOR_RED
        )
    )
    await send_log(
        interaction.guild, "🎭・logs-cargos",
        "⬇️ Rebaixamento",
        f"{membro.mention} perdeu {cargo.mention} por {interaction.user.mention}.",
        COLOR_RED
    )


# ============================================================
# PDF SIMPLES SEM DEPENDÊNCIA EXTERNA
# ============================================================

def _pdf_escape(text: str):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_simple_pdf(title: str, lines: list[str]):
    # PDF básico, texto Helvetica, múltiplas páginas.
    pages = []
    page_lines = 42
    for start in range(0, len(lines), page_lines):
        pages.append(lines[start:start + page_lines])
    if not pages:
        pages = [["Sem dados."]]

    objects = []
    # 1 catalog, 2 pages tree, 3 font
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    page_obj_numbers = []
    content_obj_numbers = []

    next_obj = 4
    for _ in pages:
        page_obj_numbers.append(next_obj)
        content_obj_numbers.append(next_obj + 1)
        next_obj += 2

    kids = " ".join(f"{n} 0 R" for n in page_obj_numbers)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for idx, page in enumerate(pages):
        page_num = page_obj_numbers[idx]
        content_num = content_obj_numbers[idx]

        stream_lines = [
            "BT",
            "/F1 16 Tf",
            "50 790 Td",
            f"({_pdf_escape(title)}) Tj",
            "0 -28 Td",
            "/F1 10 Tf",
        ]

        for line in page:
            clean = str(line).replace("\n", " ")
            # Latin-1 evita caracteres que quebram o PDF simples
            clean = clean.encode("latin-1", "replace").decode("latin-1")
            stream_lines.append(f"({_pdf_escape(clean[:120])}) Tj")
            stream_lines.append("0 -16 Td")

        stream_lines.append("ET")
        stream = "\n".join(stream_lines).encode("latin-1", "replace")

        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_num} 0 R >>"
        )
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n"
            + stream.decode("latin-1")
            + "\nendstream"
        )

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode())
        out.write(obj.encode("latin-1", "replace"))
        out.write(b"\nendobj\n")

    xref = out.tell()
    out.write(f"xref\n0 {len(objects)+1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode())

    out.write(
        f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode()
    )
    out.seek(0)
    return out


@bot.tree.command(name="relatorio-farm", description="Gera relatório de farm em PDF")
async def relatorio_farm(interaction: discord.Interaction):
    if not is_farm_staff(interaction.user):
        return await respond_error(interaction, "❌ Apenas responsáveis de farm podem gerar relatório.")

    await interaction.response.defer(ephemeral=True)

    conn = db()
    rows = conn.execute("""
        SELECT membro_id,item,quantidade,status,criado_em
        FROM farms WHERE guild_id=?
        ORDER BY id DESC LIMIT 300
    """, (interaction.guild.id,)).fetchall()
    conn.close()

    lines = []
    for r in rows:
        data = r["criado_em"][:10]
        lines.append(
            f"{data} | ID {r['membro_id']} | {r['item']} | Qtd {r['quantidade']} | {r['status']}"
        )

    pdf = make_simple_pdf(f"Relatorio de Farm - {FAC_NAME}", lines)
    file = discord.File(pdf, filename="relatorio_farm.pdf")

    await interaction.followup.send(
        "📄 Relatório gerado:",
        file=file,
        ephemeral=True
    )


# ============================================================
# BACKUP / RESTORE
# ============================================================

def overwrite_to_dict(overwrites):
    data = []
    for target, ow in overwrites.items():
        allow, deny = ow.pair()
        data.append({
            "type": "role" if isinstance(target, discord.Role) else "member",
            "id": target.id,
            "allow": allow.value,
            "deny": deny.value
        })
    return data


async def create_backup(guild: discord.Guild):
    payload = {
        "guild_id": guild.id,
        "guild_name": guild.name,
        "created_at": now_iso(),
        "roles": [],
        "categories": [],
        "channels": []
    }

    for role in guild.roles:
        if role.is_default() or role.managed:
            continue
        payload["roles"].append({
            "name": role.name,
            "permissions": role.permissions.value,
            "color": role.color.value,
            "hoist": role.hoist,
            "mentionable": role.mentionable,
            "position": role.position
        })

    for cat in guild.categories:
        payload["categories"].append({
            "name": cat.name,
            "position": cat.position
        })

    for ch in guild.channels:
        if isinstance(ch, discord.CategoryChannel):
            continue

        item = {
            "name": ch.name,
            "category": ch.category.name if ch.category else None,
            "position": ch.position,
            "type": "text" if isinstance(ch, discord.TextChannel) else "voice" if isinstance(ch, discord.VoiceChannel) else "other"
        }
        if isinstance(ch, discord.TextChannel):
            item["topic"] = ch.topic
            item["slowmode_delay"] = ch.slowmode_delay
        payload["channels"].append(item)

    path = BACKUP_DIR / f"backup_{guild.id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


@bot.tree.command(name="backup-criar", description="Cria um backup da estrutura do servidor")
async def backup_criar(interaction: discord.Interaction):
    if not is_staff(interaction.user):
        return await respond_error(interaction, "❌ Apenas a liderança pode criar backups.")

    await interaction.response.defer(ephemeral=True)
    path = await create_backup(interaction.guild)
    await interaction.followup.send(
        "✅ Backup da estrutura criado.",
        file=discord.File(path),
        ephemeral=True
    )


class RestoreConfirm(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=60)
        self.author_id = author_id

    @discord.ui.button(label="Restaurar estrutura", emoji="⚠️", style=discord.ButtonStyle.danger)
    async def restore(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await respond_error(interaction, "Somente quem executou pode confirmar.")

        path = BACKUP_DIR / f"backup_{interaction.guild.id}.json"
        if not path.exists():
            return await respond_error(interaction, "❌ Nenhum backup foi encontrado.")

        await interaction.response.edit_message(
            content="♻️ Restaurando itens ausentes do backup...",
            embed=None,
            view=None
        )

        payload = json.loads(path.read_text(encoding="utf-8"))

        # Restauração não destrutiva: recria somente o que estiver faltando.
        for r in sorted(payload.get("roles", []), key=lambda x: x.get("position", 0)):
            if not find_role(interaction.guild, r["name"]):
                try:
                    await interaction.guild.create_role(
                        name=r["name"],
                        permissions=discord.Permissions(r["permissions"]),
                        color=discord.Color(r["color"]),
                        hoist=r["hoist"],
                        mentionable=r["mentionable"],
                        reason=f"Restore {FAC_NAME}"
                    )
                except discord.Forbidden:
                    pass

        for c in payload.get("categories", []):
            if not discord.utils.get(interaction.guild.categories, name=c["name"]):
                try:
                    await interaction.guild.create_category(c["name"], reason=f"Restore {FAC_NAME}")
                except discord.Forbidden:
                    pass

        for ch in payload.get("channels", []):
            cat = discord.utils.get(interaction.guild.categories, name=ch.get("category")) if ch.get("category") else None

            if ch["type"] == "text" and not find_text(interaction.guild, ch["name"]):
                try:
                    await interaction.guild.create_text_channel(
                        ch["name"], category=cat,
                        topic=ch.get("topic"),
                        slowmode_delay=ch.get("slowmode_delay", 0),
                        reason=f"Restore {FAC_NAME}"
                    )
                except discord.Forbidden:
                    pass

            elif ch["type"] == "voice" and not discord.utils.get(interaction.guild.voice_channels, name=ch["name"]):
                try:
                    await interaction.guild.create_voice_channel(
                        ch["name"], category=cat, reason=f"Restore {FAC_NAME}"
                    )
                except discord.Forbidden:
                    pass

        target = find_text(interaction.guild, "💾・backups") or find_text(interaction.guild, "📊・dashboard")
        if target:
            await target.send(embed=brand_embed(
                "✅ Restauração concluída",
                "Os cargos, categorias e canais ausentes do último backup foram recriados.",
                COLOR_GREEN
            ))


@bot.tree.command(name="backup-restaurar", description="Restaura itens ausentes do último backup")
async def backup_restaurar(interaction: discord.Interaction):
    if not is_staff(interaction.user):
        return await respond_error(interaction, "❌ Apenas a liderança pode restaurar backup.")

    path = BACKUP_DIR / f"backup_{interaction.guild.id}.json"
    if not path.exists():
        return await respond_error(interaction, "❌ Ainda não existe backup para este servidor.")

    e = brand_embed(
        "⚠️ Restaurar Backup",
        "A restauração é **não destrutiva**: ela recria cargos/categorias/canais que estiverem faltando.\n"
        "Ela não apaga canais atuais.",
        COLOR_RED
    )
    await interaction.response.send_message(
        embed=e,
        view=RestoreConfirm(interaction.user.id),
        ephemeral=True
    )


@tasks.loop(hours=6)
async def automatic_backup():
    for guild in bot.guilds:
        try:
            await create_backup(guild)
        except Exception:
            traceback.print_exc()


@automatic_backup.before_loop
async def before_auto_backup():
    await bot.wait_until_ready()


# ============================================================
# EMBED / ANÚNCIO / LIMPEZA / STATUS
# ============================================================

class EmbedModal(discord.ui.Modal, title="Criar Embed"):
    titulo = discord.ui.TextInput(label="Título", max_length=200)
    descricao = discord.ui.TextInput(label="Descrição", style=discord.TextStyle.paragraph, max_length=3500)
    rodape = discord.ui.TextInput(label="Rodapé", required=False, max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            return await respond_error(interaction, "❌ Apenas a liderança pode criar anúncios.")

        e = discord.Embed(title=str(self.titulo), description=str(self.descricao), color=COLOR)
        if str(self.rodape):
            e.set_footer(text=str(self.rodape))
        else:
            e.set_footer(text=BOT_FOOTER)

        await interaction.response.send_message(
            "Escolha o canal usando `/enviar-embed canal:` após preparar o conteúdo.\n"
            "Prévia:",
            embed=e,
            ephemeral=True
        )


@bot.tree.command(name="embed", description="Abre o criador de embeds")
async def embed_command(interaction: discord.Interaction):
    if not is_staff(interaction.user):
        return await respond_error(interaction, "❌ Apenas liderança.")
    await interaction.response.send_modal(EmbedModal())


@bot.tree.command(name="enviar-embed", description="Envia um embed personalizado em um canal")
@app_commands.describe(canal="Canal", titulo="Título", descricao="Descrição")
async def enviar_embed(interaction: discord.Interaction, canal: discord.TextChannel, titulo: str, descricao: str):
    if not is_staff(interaction.user):
        return await respond_error(interaction, "❌ Apenas liderança.")

    await canal.send(embed=brand_embed(titulo, descricao))
    await interaction.response.send_message("✅ Embed enviado.", ephemeral=True)


@bot.tree.command(name="anuncio-privado", description="Envia anúncio no privado para membros de um cargo")
@app_commands.describe(cargo="Cargo alvo", titulo="Título", mensagem="Mensagem")
async def anuncio_privado(interaction: discord.Interaction, cargo: discord.Role, titulo: str, mensagem: str):
    if not is_staff(interaction.user):
        return await respond_error(interaction, "❌ Apenas a liderança pode usar.")

    await interaction.response.defer(ephemeral=True)

    enviados = 0
    falhas = 0
    e = brand_embed(titulo, mensagem)

    for member in cargo.members:
        if member.bot:
            continue
        try:
            await member.send(embed=e)
            enviados += 1
            await asyncio.sleep(0.35)
        except (discord.Forbidden, discord.HTTPException):
            falhas += 1

    await interaction.followup.send(
        f"✅ Enviados: **{enviados}**\n❌ Falhas/DM fechada: **{falhas}**",
        ephemeral=True
    )


@bot.tree.command(name="limpar", description="Limpa mensagens do canal")
@app_commands.describe(quantidade="Quantidade de mensagens para apagar")
async def limpar(interaction: discord.Interaction, quantidade: app_commands.Range[int, 1, 100] = 20):
    if not interaction.user.guild_permissions.manage_messages:
        return await respond_error(interaction, "❌ Você precisa da permissão Gerenciar Mensagens.")

    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=quantidade)
    await interaction.followup.send(f"🧹 **{len(deleted)}** mensagens removidas.", ephemeral=True)


@bot.tree.command(name="status-bot", description="Altera o status exibido pelo bot")
async def status_bot(interaction: discord.Interaction, texto: str):
    if not interaction.user.guild_permissions.administrator:
        return await respond_error(interaction, "❌ Apenas administrador.")

    setting_set(interaction.guild.id, "bot_status", texto)
    await bot.change_presence(activity=discord.Game(name=texto))
    await interaction.response.send_message(f"✅ Status alterado para **{texto}**.", ephemeral=True)


@bot.tree.command(name="nome-bot-servidor", description="Altera o apelido do bot neste servidor")
async def nome_bot_servidor(interaction: discord.Interaction, nome: str):
    if not interaction.user.guild_permissions.administrator:
        return await respond_error(interaction, "❌ Apenas administrador.")

    try:
        await interaction.guild.me.edit(nick=nome[:32])
        await interaction.response.send_message("✅ Nome/apelido do bot alterado neste servidor.", ephemeral=True)
    except discord.Forbidden:
        await respond_error(interaction, "❌ Não consegui alterar meu apelido. Verifique minhas permissões.")


# ============================================================
# PAINÉIS / SETUP / DASHBOARD
# ============================================================

@bot.tree.command(name="setup-servidor", description="Cria/atualiza cargos, canais e permissões do sistema")
@app_commands.default_permissions(administrator=True)
async def setup_servidor(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    try:
        await ensure_structure(interaction.guild)

        # Painel principal
        reg_ch = find_text(interaction.guild, "📝・registro")
        if reg_ch:
            e = brand_embed(
                f"📝 Central de {FAC_NAME}",
                "Bem-vindo à central da organização.\n\n"
                "Utilize os botões abaixo para acessar os sistemas de **registro, visitante, farm, ausência e ranking**.\n\n"
                "Todos os formulários são enviados diretamente para os responsáveis."
            )
            await reg_ch.send(embed=e, view=MainPanel())

        # Dashboard
        dash = find_text(interaction.guild, "📊・dashboard")
        if dash:
            await dash.send(embed=await build_dashboard_embed(interaction.guild), view=ManagementPanel())

        await update_ranking_farm(interaction.guild)

        await interaction.followup.send(
            "✅ Estrutura atualizada e painéis enviados.\n"
            "Use `/dashboard` para abrir a gestão em qualquer canal.",
            ephemeral=True
        )
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(
            f"❌ Erro no setup:\n```{type(e).__name__}: {e}```",
            ephemeral=True
        )


@bot.tree.command(name="painel", description="Envia o painel principal da facção")
@app_commands.default_permissions(administrator=True)
async def painel(interaction: discord.Interaction):
    e = brand_embed(
        f"📝 Central de {FAC_NAME}",
        "Selecione abaixo o sistema que deseja acessar."
    )
    await interaction.channel.send(embed=e, view=MainPanel())
    await interaction.response.send_message("✅ Painel enviado.", ephemeral=True)


@bot.tree.command(name="dashboard", description="Abre o dashboard administrativo")
async def dashboard(interaction: discord.Interaction):
    if not is_staff(interaction.user):
        return await respond_error(interaction, "❌ Este dashboard é exclusivo da liderança.")

    await interaction.response.send_message(
        embed=await build_dashboard_embed(interaction.guild),
        view=ManagementPanel(),
        ephemeral=True
    )


@bot.tree.command(name="ranking", description="Mostra ranking geral de membros")
async def ranking(interaction: discord.Interaction):
    conn = db()
    rows = conn.execute("""
        SELECT membro_id,pontos FROM pontos
        WHERE guild_id=?
        ORDER BY pontos DESC LIMIT 15
    """, (interaction.guild.id,)).fetchall()
    conn.close()

    lines = []
    for i, r in enumerate(rows):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"`{i+1:02}`"
        lines.append(f"{medal} <@{r['membro_id']}> — **{r['pontos']} pts**")

    await interaction.response.send_message(
        embed=brand_embed("🏆 Ranking Geral", "\n".join(lines) if lines else "Sem pontuação ainda.")
    )


@bot.tree.command(name="hierarquia", description="Mostra a hierarquia da facção")
async def hierarquia(interaction: discord.Interaction):
    names = [r[0] for r in ROLE_DEFS]
    lines = []
    for name in names:
        role = find_role(interaction.guild, name)
        if role:
            lines.append(f"{role.mention} — **{len(role.members)}** membro(s)")
    await interaction.response.send_message(
        embed=brand_embed("🎭 Hierarquia", "\n".join(lines))
    )


@bot.tree.command(name="ajuda", description="Mostra a central de ajuda e comandos")
async def ajuda(interaction: discord.Interaction):
    text = (
        "**Painéis**\n"
        "`/painel` — painel dos membros\n"
        "`/dashboard` — painel administrativo\n"
        "`/setup-servidor` — estrutura e permissões\n\n"
        "**Membros**\n"
        "`/advertir` • `/advertencias` • `/promover` • `/rebaixar` • `/hierarquia`\n\n"
        "**Gestão**\n"
        "`/ranking` • `/relatorio-farm` • `/embed` • `/enviar-embed`\n"
        "`/anuncio-privado` • `/limpar`\n\n"
        "**Backup e Configuração**\n"
        "`/backup-criar` • `/backup-restaurar` • `/status-bot` • `/nome-bot-servidor`"
    )
    await interaction.response.send_message(embed=brand_embed("❓ Central de Ajuda", text), ephemeral=True)


# ============================================================
# ANTI-SPAM / ANTI-RAID
# ============================================================

spam_tracker = defaultdict(lambda: deque(maxlen=10))
join_tracker = defaultdict(lambda: deque(maxlen=20))
raid_locked = set()


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    now = time.monotonic()
    q = spam_tracker[(message.guild.id, message.author.id)]
    q.append(now)

    # 6 mensagens em até 5 segundos
    if len(q) >= 6 and q[-1] - q[-6] <= 5:
        member = message.author
        try:
            until = discord.utils.utcnow() + timedelta(seconds=45)
            await member.timeout(until, reason="Anti-spam automático")
            q.clear()
            await send_log(
                message.guild, "🛡️・logs-segurança",
                "🚫 Anti-Spam",
                f"{member.mention} foi silenciado por **45 segundos** por spam.",
                COLOR_RED
            )
        except discord.Forbidden:
            pass

    await bot.process_commands(message)


async def activate_raid_lock(guild: discord.Guild):
    if guild.id in raid_locked:
        return
    raid_locked.add(guild.id)

    for ch in guild.text_channels:
        # Não bloqueia canais de logs/liderança
        if ch.category and ch.category.name in {"👑・LIDERANÇA", "🛡️・LOGS"}:
            continue
        try:
            ow = ch.overwrites_for(guild.default_role)
            ow.send_messages = False
            await ch.set_permissions(guild.default_role, overwrite=ow, reason="Anti-raid automático")
        except discord.Forbidden:
            pass

    await send_log(
        guild, "🛡️・logs-segurança",
        "🚨 Anti-Raid Ativado",
        "Muitas entradas foram detectadas em poucos segundos. "
        "Os canais públicos foram temporariamente bloqueados.\n"
        "Use `/desbloquear-raid` para liberar.",
        COLOR_RED
    )


@bot.tree.command(name="desbloquear-raid", description="Desativa o bloqueio de emergência do anti-raid")
@app_commands.default_permissions(administrator=True)
async def desbloquear_raid(interaction: discord.Interaction):
    for ch in interaction.guild.text_channels:
        if ch.category and ch.category.name in {"👑・LIDERANÇA", "🛡️・LOGS"}:
            continue
        try:
            ow = ch.overwrites_for(interaction.guild.default_role)
            if ow.send_messages is False:
                ow.send_messages = None
                await ch.set_permissions(interaction.guild.default_role, overwrite=ow, reason="Anti-raid liberado")
        except discord.Forbidden:
            pass

    raid_locked.discard(interaction.guild.id)
    await interaction.response.send_message("✅ Bloqueio do anti-raid removido.", ephemeral=True)


# ============================================================
# LOGS
# ============================================================

@bot.event
async def on_member_join(member: discord.Member):
    # Visitante por padrão
    visitor = find_role(member.guild, "👤 Visitante")
    if visitor:
        try:
            await member.add_roles(visitor, reason="Entrada automática")
        except discord.Forbidden:
            pass

    ch = find_text(member.guild, "👋・boas-vindas")
    if ch:
        e = brand_embed(
            f"👋 Bem-vindo(a), {member.display_name}!",
            f"{member.mention}, seja bem-vindo(a) ao **{member.guild.name}**.\n"
            "Vá até o canal de registro e utilize o painel.",
            COLOR_GREEN
        )
        if member.display_avatar:
            e.set_thumbnail(url=member.display_avatar.url)
        await ch.send(embed=e)

    await send_log(
        member.guild, "👥・logs-membros",
        "📥 Entrada",
        f"{member.mention} entrou no servidor.\nID: `{member.id}`",
        COLOR_GREEN
    )

    q = join_tracker[member.guild.id]
    q.append(time.monotonic())
    if len(q) >= 10 and q[-1] - q[-10] <= 15:
        await activate_raid_lock(member.guild)


@bot.event
async def on_member_remove(member: discord.Member):
    await send_log(
        member.guild, "👥・logs-membros",
        "📤 Saída",
        f"**{member}** saiu do servidor.\nID: `{member.id}`",
        COLOR_RED
    )


@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    await send_log(
        guild, "👥・logs-membros",
        "🔨 Banimento",
        f"**{user}** foi banido.\nID: `{user.id}`",
        COLOR_RED
    )


@bot.event
async def on_member_unban(guild: discord.Guild, user: discord.User):
    await send_log(
        guild, "👥・logs-membros",
        "🔓 Desbanimento",
        f"**{user}** foi desbanido.\nID: `{user.id}`",
        COLOR_GREEN
    )


@bot.event
async def on_message_delete(message: discord.Message):
    if not message.guild or message.author.bot:
        return

    content = message.content or "*sem conteúdo de texto*"
    if len(content) > 1500:
        content = content[:1500] + "..."

    await send_log(
        message.guild, "💬・logs-mensagens",
        "🗑️ Mensagem apagada",
        f"**Autor:** {message.author.mention}\n"
        f"**Canal:** {message.channel.mention}\n"
        f"**Conteúdo:**\n{content}",
        COLOR_RED
    )


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if not before.guild or before.author.bot or before.content == after.content:
        return

    b = (before.content or "*vazio*")[:700]
    a = (after.content or "*vazio*")[:700]
    await send_log(
        before.guild, "💬・logs-mensagens",
        "✏️ Mensagem editada",
        f"**Autor:** {before.author.mention}\n"
        f"**Canal:** {before.channel.mention}\n"
        f"**Antes:** {b}\n"
        f"**Depois:** {a}"
    )


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if before.channel == after.channel:
        return

    if before.channel is None and after.channel:
        text = f"{member.mention} entrou em **{after.channel.name}**."
    elif before.channel and after.channel is None:
        text = f"{member.mention} saiu de **{before.channel.name}**."
    else:
        text = f"{member.mention} moveu de **{before.channel.name}** para **{after.channel.name}**."

    await send_log(member.guild, "🔊・logs-voz", "🔊 Voz", text, COLOR_BLUE)


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    before_roles = set(before.roles)
    after_roles = set(after.roles)

    added = after_roles - before_roles
    removed = before_roles - after_roles

    if added:
        await send_log(
            after.guild, "🎭・logs-cargos",
            "➕ Cargo adicionado",
            f"{after.mention}: " + ", ".join(r.mention for r in added)
        )
    if removed:
        await send_log(
            after.guild, "🎭・logs-cargos",
            "➖ Cargo removido",
            f"{after.mention}: " + ", ".join(r.mention for r in removed)
        )


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():
    try:
        init_db()

        # Views persistentes: botões continuam funcionando após reinício.
        bot.add_view(MainPanel())
        bot.add_view(ManagementPanel())
        bot.add_view(RegistroApprovalView())
        bot.add_view(FarmApprovalView())
        bot.add_view(AusenciaApprovalView())

        if GUILD_ID and GUILD_ID.isdigit():
            guild_obj = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild_obj)
            await bot.tree.sync(guild=guild_obj)
        else:
            await bot.tree.sync()

        # Status salvo
        if bot.guilds:
            status = setting_get(bot.guilds[0].id, "bot_status", f"Gerenciando {FAC_NAME}")
        else:
            status = f"Gerenciando {FAC_NAME}"
        await bot.change_presence(activity=discord.Game(name=status))

        if not automatic_backup.is_running():
            automatic_backup.start()

        print(f"✅ Online como {bot.user} | {len(bot.guilds)} servidor(es)")

    except Exception:
        traceback.print_exc()


bot.run(TOKEN)

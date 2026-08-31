import os
import sqlite3
import traceback
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

if not TOKEN:
    raise RuntimeError("Configure DISCORD_TOKEN nas variáveis do Railway ou no .env")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

DB_PATH = "faccao.db"

# =========================================================
# CONFIGURAÇÃO
# =========================================================

ROLES = [
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
    ("🛡️ Sub-Líder", discord.Permissions(
        manage_messages=True
    )),
    ("💼 Gerente de Farm", discord.Permissions(
        manage_messages=True
    )),
    ("🎯 Gerente de Ação", discord.Permissions(
        manage_messages=True
    )),
    ("🔴 Membro", discord.Permissions()),
    ("🆕 Recruta", discord.Permissions()),
    ("💤 Ausente", discord.Permissions()),
    ("🤝 Parceiro", discord.Permissions()),
    ("👤 Visitante", discord.Permissions()),
]

LEADERSHIP_NAMES = {
    "👑 Dono", "👑 Sub-Dono", "⚜️ Gerente", "🔱 Líder", "🛡️ Sub-Líder"
}

FARM_MANAGER_NAMES = LEADERSHIP_NAMES | {"💼 Gerente de Farm"}
ACTION_MANAGER_NAMES = LEADERSHIP_NAMES | {"🎯 Gerente de Ação"}

STRUCTURE = {
    "📌・INFORMAÇÕES": [
        ("📜・regras", "text"),
        ("📢・anúncios", "text"),
        ("📋・informações", "text"),
        ("🎭・hierarquia", "text"),
        ("🆘・suporte", "text"),
    ],
    "🏘️・COMUNIDADE": [
        ("💬・chat-geral", "text"),
        ("📸・mídias", "text"),
        ("😂・resenha", "text"),
        ("💡・sugestões", "text"),
        ("🤖・comandos", "text"),
    ],
    "📝・REGISTRO": [
        ("📝・registro", "text"),
        ("⏳・registros-pendentes", "text"),
        ("👤・visitantes", "text"),
        ("👋・boas-vindas", "text"),
    ],
    "📦・FARM": [
        ("📦・painel-farm", "text"),
        ("⏳・aprovação-farm", "text"),
        ("🏆・ranking-farm", "text"),
        ("🎯・metas", "text"),
        ("📊・relatórios-farm", "text"),
    ],
    "💰・GESTÃO": [
        ("📦・estoque", "text"),
        ("🔐・baú-liderança", "text"),
        ("🏦・banco", "text"),
        ("💵・vendas", "text"),
        ("📋・encomendas", "text"),
        ("💸・lavagem", "text"),
        ("📊・ranking-geral", "text"),
    ],
    "🎯・AÇÕES": [
        ("📋・painel-ações", "text"),
        ("📅・ações-marcadas", "text"),
        ("📸・resultados", "text"),
        ("🏆・ranking-ações", "text"),
    ],
    "💤・AUSÊNCIA": [
        ("📋・solicitar-ausência", "text"),
        ("⏳・aprovação-ausência", "text"),
    ],
    "👑・LIDERANÇA": [
        ("💬・chat-liderança", "text"),
        ("👥・gerenciar-membros", "text"),
        ("⬆️・promoções-rebaixamentos", "text"),
        ("⚠️・advertências", "text"),
        ("📊・relatórios", "text"),
        ("📢・anúncio-privado", "text"),
        ("🎨・criador-de-embeds", "text"),
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
        ("🎯・Ação 03", "voice"),
        ("👑・Liderança", "voice"),
        ("💤・AFK", "voice"),
    ],
}


# =========================================================
# BANCO DE DADOS
# =========================================================

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS advertencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            membro_id INTEGER NOT NULL,
            motivo TEXT NOT NULL,
            autor_id INTEGER NOT NULL,
            criado_em TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS farms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            membro_id INTEGER NOT NULL,
            item TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            status TEXT DEFAULT 'pendente',
            aprovado_por INTEGER,
            criado_em TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ausencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            membro_id INTEGER NOT NULL,
            motivo TEXT NOT NULL,
            periodo TEXT NOT NULL,
            status TEXT DEFAULT 'pendente',
            aprovado_por INTEGER,
            criado_em TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS financeiro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            membro_id INTEGER,
            valor REAL NOT NULL,
            descricao TEXT,
            autor_id INTEGER NOT NULL,
            criado_em TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS acoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            horario TEXT NOT NULL,
            descricao TEXT,
            autor_id INTEGER NOT NULL,
            resultado TEXT,
            criado_em TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# HELPERS
# =========================================================

def now():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def get_channel(guild: discord.Guild, name: str):
    return discord.utils.get(guild.text_channels, name=name)


def has_any_role(member: discord.Member, names: set[str]) -> bool:
    if member.guild_permissions.administrator:
        return True
    return any(role.name in names for role in member.roles)


async def safe_send(channel, *args, **kwargs):
    if channel:
        try:
            return await channel.send(*args, **kwargs)
        except discord.HTTPException:
            pass


async def log(guild: discord.Guild, channel_name: str, title: str, description: str):
    channel = get_channel(guild, channel_name)
    if not channel:
        return
    embed = discord.Embed(
        title=title,
        description=description,
        timestamp=datetime.now()
    )
    await safe_send(channel, embed=embed)


async def ensure_roles(guild: discord.Guild):
    roles = {}
    for name, perms in ROLES:
        role = discord.utils.get(guild.roles, name=name)
        if role is None:
            role = await guild.create_role(
                name=name,
                permissions=perms,
                reason="Setup Bot Facção Pro"
            )
        roles[name] = role
    return roles


def overwrites_for_category(guild: discord.Guild, roles: dict, category_name: str):
    everyone = guild.default_role

    member = roles["🔴 Membro"]
    recruit = roles["🆕 Recruta"]
    visitor = roles["👤 Visitante"]
    partner = roles["🤝 Parceiro"]
    absent = roles["💤 Ausente"]

    leadership = [roles[n] for n in LEADERSHIP_NAMES]
    farm_managers = [roles[n] for n in FARM_MANAGER_NAMES]
    action_managers = [roles[n] for n in ACTION_MANAGER_NAMES]

    def deny_all():
        return {everyone: discord.PermissionOverwrite(view_channel=False)}

    # Informação: todos veem, apenas liderança fala nos principais canais.
    if category_name == "📌・INFORMAÇÕES":
        ow = {
            everyone: discord.PermissionOverwrite(view_channel=True),
            visitor: discord.PermissionOverwrite(view_channel=True),
            recruit: discord.PermissionOverwrite(view_channel=True),
            member: discord.PermissionOverwrite(view_channel=True),
        }
        return ow

    # Comunidade para membros/recrutas/parceiros.
    if category_name == "🏘️・COMUNIDADE":
        ow = deny_all()
        for role in [member, recruit, partner, absent] + leadership:
            ow[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        return ow

    # Registro: visitante e recruta conseguem acessar.
    if category_name == "📝・REGISTRO":
        ow = deny_all()
        for role in [visitor, recruit, member] + leadership:
            ow[role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True
            )
        return ow

    # Farm: membros veem, gerência aprova.
    if category_name == "📦・FARM":
        ow = deny_all()
        for role in [member, recruit, absent]:
            ow[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        for role in farm_managers:
            ow[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_messages=True,
                read_message_history=True
            )
        return ow

    # Gestão: liderança.
    if category_name == "💰・GESTÃO":
        ow = deny_all()
        for role in leadership:
            ow[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        return ow

    # Ações: membros veem; gerentes de ação gerenciam.
    if category_name == "🎯・AÇÕES":
        ow = deny_all()
        for role in [member, recruit, absent]:
            ow[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        for role in action_managers:
            ow[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_messages=True,
                read_message_history=True
            )
        return ow

    # Ausência: membros podem solicitar.
    if category_name == "💤・AUSÊNCIA":
        ow = deny_all()
        for role in [member, recruit, absent] + leadership:
            ow[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        return ow

    # Liderança e logs: só liderança.
    if category_name in {"👑・LIDERANÇA", "🛡️・LOGS"}:
        ow = deny_all()
        for role in leadership:
            ow[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        return ow

    # Calls: membros/recrutas/liderança.
    if category_name == "🔊・CALLS":
        ow = deny_all()
        for role in [member, recruit, partner, absent] + leadership:
            ow[role] = discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True
            )
        return ow

    return None


async def configure_special_channels(guild: discord.Guild, roles: dict):
    everyone = guild.default_role

    # Canais de anúncios/regras: somente liderança fala.
    for name in ["📜・regras", "📢・anúncios", "📋・informações", "🎭・hierarquia"]:
        channel = get_channel(guild, name)
        if channel:
            await channel.set_permissions(everyone, view_channel=True, send_messages=False)
            for role_name in LEADERSHIP_NAMES:
                await channel.set_permissions(
                    roles[role_name],
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

    # Pendências de registro privadas.
    pending = get_channel(guild, "⏳・registros-pendentes")
    if pending:
        await pending.set_permissions(everyone, view_channel=False)
        for role_name in LEADERSHIP_NAMES:
            await pending.set_permissions(
                roles[role_name],
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

    # Aprovação de farm privada para gerentes.
    pending_farm = get_channel(guild, "⏳・aprovação-farm")
    if pending_farm:
        await pending_farm.set_permissions(everyone, view_channel=False)
        for role_name in FARM_MANAGER_NAMES:
            await pending_farm.set_permissions(
                roles[role_name],
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

    # Aprovação de ausência privada.
    pending_absence = get_channel(guild, "⏳・aprovação-ausência")
    if pending_absence:
        await pending_absence.set_permissions(everyone, view_channel=False)
        for role_name in LEADERSHIP_NAMES:
            await pending_absence.set_permissions(
                roles[role_name],
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )


async def build_server(guild: discord.Guild):
    roles = await ensure_roles(guild)
    created = []

    for category_name, channels in STRUCTURE.items():
        category = discord.utils.get(guild.categories, name=category_name)
        ow = overwrites_for_category(guild, roles, category_name)

        if category is None:
            if ow:
                category = await guild.create_category(
                    category_name,
                    overwrites=ow,
                    reason="Setup Bot Facção Pro"
                )
            else:
                category = await guild.create_category(
                    category_name,
                    reason="Setup Bot Facção Pro"
                )
            created.append(category_name)
        elif ow:
            await category.edit(overwrites=ow, reason="Atualizando permissões Facção Pro")

        for channel_name, kind in channels:
            existing = discord.utils.get(category.channels, name=channel_name)
            if existing:
                continue

            if kind == "voice":
                await guild.create_voice_channel(
                    channel_name,
                    category=category,
                    reason="Setup Bot Facção Pro"
                )
            else:
                await guild.create_text_channel(
                    channel_name,
                    category=category,
                    reason="Setup Bot Facção Pro"
                )
            created.append(channel_name)

    await configure_special_channels(guild, roles)
    return created


# =========================================================
# REGISTRO
# =========================================================

class RegistroModal(discord.ui.Modal, title="Registro na Facção"):
    nome = discord.ui.TextInput(label="Nome / Vulgo", max_length=40)
    passaporte = discord.ui.TextInput(label="Passaporte / ID", max_length=20)
    telefone = discord.ui.TextInput(label="Telefone", required=False, max_length=30)
    recrutador = discord.ui.TextInput(label="Quem te recrutou?", required=False, max_length=40)

    async def on_submit(self, interaction: discord.Interaction):
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO registros
            (discord_id, nome, passaporte, telefone, recrutador, criado_em)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                interaction.user.id,
                str(self.nome),
                str(self.passaporte),
                str(self.telefone),
                str(self.recrutador),
                now()
            )
        )
        registro_id = cur.lastrowid
        conn.commit()
        conn.close()

        embed = discord.Embed(
            title=f"📝 Novo Registro #{registro_id}",
            description=f"Solicitação enviada por {interaction.user.mention}"
        )
        embed.add_field(name="Nome / Vulgo", value=str(self.nome), inline=False)
        embed.add_field(name="Passaporte / ID", value=str(self.passaporte), inline=True)
        embed.add_field(name="Telefone", value=str(self.telefone) or "Não informado", inline=True)
        embed.add_field(name="Recrutador", value=str(self.recrutador) or "Não informado", inline=False)

        pending = get_channel(interaction.guild, "⏳・registros-pendentes")
        if pending:
            await pending.send(
                embed=embed,
                view=RegistroApprovalView(registro_id, interaction.user.id)
            )

        await interaction.response.send_message(
            "✅ Seu registro foi enviado para análise.",
            ephemeral=True
        )


class RegistroApprovalView(discord.ui.View):
    def __init__(self, registro_id: int, user_id: int):
        super().__init__(timeout=None)
        self.registro_id = registro_id
        self.user_id = user_id

    @discord.ui.button(label="Aprovar", style=discord.ButtonStyle.success, emoji="✅")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_any_role(interaction.user, LEADERSHIP_NAMES):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)

        member = interaction.guild.get_member(self.user_id)
        role_member = discord.utils.get(interaction.guild.roles, name="🔴 Membro")
        role_recruit = discord.utils.get(interaction.guild.roles, name="🆕 Recruta")
        role_visitor = discord.utils.get(interaction.guild.roles, name="👤 Visitante")

        if member:
            if role_member:
                await member.add_roles(role_member, reason="Registro aprovado")
            for role in [role_recruit, role_visitor]:
                if role and role in member.roles:
                    await member.remove_roles(role, reason="Registro aprovado")

        conn = db()
        conn.execute(
            "UPDATE registros SET status='aprovado', aprovado_por=? WHERE id=?",
            (interaction.user.id, self.registro_id)
        )
        conn.commit()
        conn.close()

        await interaction.response.edit_message(
            content=f"✅ Registro aprovado por {interaction.user.mention}",
            embed=interaction.message.embeds[0] if interaction.message.embeds else None,
            view=None
        )

        welcome = get_channel(interaction.guild, "👋・boas-vindas")
        if welcome and member:
            await welcome.send(f"👋 Bem-vindo à facção, {member.mention}!")

        await log(
            interaction.guild,
            "👥・logs-membros",
            "✅ Registro aprovado",
         

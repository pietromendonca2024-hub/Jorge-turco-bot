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
            f"{member.mention if member else self.user_id} aprovado por {interaction.user.mention}"
        )

    @discord.ui.button(label="Reprovar", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_any_role(interaction.user, LEADERSHIP_NAMES):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)

        conn = db()
        conn.execute(
            "UPDATE registros SET status='reprovado', aprovado_por=? WHERE id=?",
            (interaction.user.id, self.registro_id)
        )
        conn.commit()
        conn.close()

        await interaction.response.edit_message(
            content=f"❌ Registro reprovado por {interaction.user.mention}",
            embed=interaction.message.embeds[0] if interaction.message.embeds else None,
            view=None
        )


# =========================================================
# FARM
# =========================================================

class FarmModal(discord.ui.Modal, title="Enviar Farm"):
    item = discord.ui.TextInput(label="Item farmado", max_length=60)
    quantidade = discord.ui.TextInput(label="Quantidade", max_length=10)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qtd = int(str(self.quantidade))
            if qtd <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "❌ Quantidade inválida.",
                ephemeral=True
            )

        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO farms (membro_id, item, quantidade, criado_em)
            VALUES (?, ?, ?, ?)
            """,
            (interaction.user.id, str(self.item), qtd, now())
        )
        farm_id = cur.lastrowid
        conn.commit()
        conn.close()

        embed = discord.Embed(title=f"📦 Farm #{farm_id}")
        embed.add_field(name="Membro", value=interaction.user.mention, inline=False)
        embed.add_field(name="Item", value=str(self.item), inline=True)
        embed.add_field(name="Quantidade", value=str(qtd), inline=True)

        pending = get_channel(interaction.guild, "⏳・aprovação-farm")
        if pending:
            await pending.send(
                embed=embed,
                view=FarmApprovalView(farm_id, interaction.user.id, qtd)
            )

        await interaction.response.send_message(
            "✅ Farm enviado para aprovação.",
            ephemeral=True
        )


class FarmApprovalView(discord.ui.View):
    def __init__(self, farm_id: int, member_id: int, amount: int):
        super().__init__(timeout=None)
        self.farm_id = farm_id
        self.member_id = member_id
        self.amount = amount

    @discord.ui.button(label="Aprovar", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_any_role(interaction.user, FARM_MANAGER_NAMES):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)

        conn = db()
        conn.execute(
            "UPDATE farms SET status='aprovado', aprovado_por=? WHERE id=?",
            (interaction.user.id, self.farm_id)
        )
        conn.commit()
        conn.close()

        await interaction.response.edit_message(
            content=f"✅ Farm aprovado por {interaction.user.mention}",
            embed=interaction.message.embeds[0] if interaction.message.embeds else None,
            view=None
        )

        await log(
            interaction.guild,
            "📦・logs-farm",
            "📦 Farm aprovado",
            f"<@{self.member_id}> • quantidade: **{self.amount}** • aprovado por {interaction.user.mention}"
        )

    @discord.ui.button(label="Reprovar", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_any_role(interaction.user, FARM_MANAGER_NAMES):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)

        conn = db()
        conn.execute(
            "UPDATE farms SET status='reprovado', aprovado_por=? WHERE id=?",
            (interaction.user.id, self.farm_id)
        )
        conn.commit()
        conn.close()

        await interaction.response.edit_message(
            content=f"❌ Farm reprovado por {interaction.user.mention}",
            embed=interaction.message.embeds[0] if interaction.message.embeds else None,
            view=None
        )


# =========================================================
# AUSÊNCIA
# =========================================================

class AusenciaModal(discord.ui.Modal, title="Solicitar Ausência"):
    motivo = discord.ui.TextInput(label="Motivo", style=discord.TextStyle.paragraph, max_length=300)
    periodo = discord.ui.TextInput(label="Período", placeholder="Ex.: 01/09 até 05/09", max_length=60)

    async def on_submit(self, interaction: discord.Interaction):
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ausencias (membro_id, motivo, periodo, criado_em)
            VALUES (?, ?, ?, ?)
            """,
            (interaction.user.id, str(self.motivo), str(self.periodo), now())
        )
        absence_id = cur.lastrowid
        conn.commit()
        conn.close()

        embed = discord.Embed(title=f"💤 Ausência #{absence_id}")
        embed.add_field(name="Membro", value=interaction.user.mention, inline=False)
        embed.add_field(name="Período", value=str(self.periodo), inline=False)
        embed.add_field(name="Motivo", value=str(self.motivo), inline=False)

        pending = get_channel(interaction.guild, "⏳・aprovação-ausência")
        if pending:
            await pending.send(
                embed=embed,
                view=AusenciaApprovalView(absence_id, interaction.user.id)
            )

        await interaction.response.send_message(
            "✅ Solicitação de ausência enviada.",
            ephemeral=True
        )


class AusenciaApprovalView(discord.ui.View):
    def __init__(self, absence_id: int, member_id: int):
        super().__init__(timeout=None)
        self.absence_id = absence_id
        self.member_id = member_id

    @discord.ui.button(label="Aprovar", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_any_role(interaction.user, LEADERSHIP_NAMES):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)

        member = interaction.guild.get_member(self.member_id)
        absent_role = discord.utils.get(interaction.guild.roles, name="💤 Ausente")
        if member and absent_role:
            await member.add_roles(absent_role, reason="Ausência aprovada")

        conn = db()
        conn.execute(
            "UPDATE ausencias SET status='aprovado', aprovado_por=? WHERE id=?",
            (interaction.user.id, self.absence_id)
        )
        conn.commit()
        conn.close()

        await interaction.response.edit_message(
            content=f"✅ Ausência aprovada por {interaction.user.mention}",
            embed=interaction.message.embeds[0] if interaction.message.embeds else None,
            view=None
        )

    @discord.ui.button(label="Reprovar", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_any_role(interaction.user, LEADERSHIP_NAMES):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)

        conn = db()
        conn.execute(
            "UPDATE ausencias SET status='reprovado', aprovado_por=? WHERE id=?",
            (interaction.user.id, self.absence_id)
        )
        conn.commit()
        conn.close()

        await interaction.response.edit_message(
            content=f"❌ Ausência reprovada por {interaction.user.mention}",
            embed=interaction.message.embeds[0] if interaction.message.embeds else None,
            view=None
        )


# =========================================================
# PAINEL PRINCIPAL
# =========================================================

class MainPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Registro", style=discord.ButtonStyle.primary, emoji="📝", custom_id="fac:registro")
    async def registro(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegistroModal())

    @discord.ui.button(label="Enviar Farm", style=discord.ButtonStyle.success, emoji="📦", custom_id="fac:farm")
    async def farm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FarmModal())

    @discord.ui.button(label="Solicitar Ausência", style=discord.ButtonStyle.secondary, emoji="💤", custom_id="fac:ausencia")
    async def ausencia(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AusenciaModal())


# =========================================================
# COMANDOS
# =========================================================

@bot.tree.command(name="painel-faccao", description="Envia o painel principal da facção")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def painel_faccao(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔴 JORGE TURCO • Painel da Facção",
        description=(
            "Use os botões abaixo para acessar os sistemas da facção.\n\n"
            "📝 **Registro** — enviar cadastro\n"
            "📦 **Farm** — enviar farm para aprovação\n"
            "💤 **Ausência** — solicitar ausência"
        )
    )
    await interaction.response.send_message(embed=embed, view=MainPanel())


@bot.tree.command(name="setup-servidor", description="Cria/atualiza estrutura e permissões da facção")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def setup_servidor(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        created = await build_server(interaction.guild)
        await interaction.followup.send(
            f"✅ Estrutura atualizada. **{len(created)}** itens novos criados.\n"
            "As permissões por categoria e cargos também foram aplicadas.",
            ephemeral=True
        )
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(
            f"❌ Erro: `{type(e).__name__}: {e}`",
            ephemeral=True
        )


@bot.tree.command(name="advertir", description="Aplica advertência em um membro")
@app_commands.describe(membro="Membro advertido", motivo="Motivo da advertência")
@app_commands.guild_only()
async def advertir(interaction: discord.Interaction, membro: discord.Member, motivo: str):
    if not has_any_role(interaction.user, LEADERSHIP_NAMES):
        return await interaction.response.send_message("Sem permissão.", ephemeral=True)

    conn = db()
    conn.execute(
        "INSERT INTO advertencias (membro_id, motivo, autor_id, criado_em) VALUES (?, ?, ?, ?)",
        (membro.id, motivo, interaction.user.id, now())
    )
    conn.commit()
    conn.close()

    await interaction.response.send_message(
        f"⚠️ {membro.mention} recebeu uma advertência.",
        ephemeral=True
    )

    channel = get_channel(interaction.guild, "⚠️・advertências")
    await safe_send(
        channel,
        embed=discord.Embed(
            title="⚠️ Advertência",
            description=f"**Membro:** {membro.mention}\n**Motivo:** {motivo}\n**Aplicada por:** {interaction.user.mention}"
        )
    )


@bot.tree.command(name="advertencias", description="Consulta advertências de um membro")
@app_commands.guild_only()
async def advertencias(interaction: discord.Interaction, membro: discord.Member):
    if not has_any_role(interaction.user, LEADERSHIP_NAMES):
        return await interaction.response.send_message("Sem permissão.", ephemeral=True)

    conn = db()
    rows = conn.execute(
        "SELECT * FROM advertencias WHERE membro_id=? ORDER BY id DESC LIMIT 10",
        (membro.id,)
    ).fetchall()
    conn.close()

    if not rows:
        return await interaction.response.send_message(
            f"✅ {membro.mention} não possui advertências registradas.",
            ephemeral=True
        )

    text = "\n".join(
        f"`#{r['id']}` {r['motivo']} — {r['criado_em']}"
        for r in rows
    )
    await interaction.response.send_message(
        f"⚠️ **Advertências de {membro.display_name}:**\n{text}",
        ephemeral=True
    )


@bot.tree.command(name="promover", description="Promove um membro para um cargo")
@app_commands.describe(membro="Membro", cargo="Cargo novo")
@app_commands.guild_only()
async def promover(interaction: discord.Interaction, membro: discord.Member, cargo: discord.Role):
    if not has_any_role(interaction.user, LEADERSHIP_NAMES):
        return await interaction.response.send_message("Sem permissão.", ephemeral=True)

    if cargo >= interaction.guild.me.top_role:
        return await interaction.response.send_message(
            "❌ Esse cargo está acima ou igual ao cargo do bot.",
            ephemeral=True
        )

    await membro.add_roles(cargo, reason=f"Promoção por {interaction.user}")
    await interaction.response.send_message(
        f"⬆️ {membro.mention} recebeu o cargo {cargo.mention}.",
        ephemeral=True
    )

    await log(
        interaction.guild,
        "🎭・logs-cargos",
        "⬆️ Promoção",
        f"{membro.mention} → {cargo.mention}\nPor: {interaction.user.mention}"
    )


@bot.tree.command(name="rebaixar", description="Remove um cargo de um membro")
@app_commands.describe(membro="Membro", cargo="Cargo que será removido")
@app_commands.guild_only()
async def rebaixar(interaction: discord.Interaction, membro: discord.Member, cargo: discord.Role):
    if not has_any_role(interaction.user, LEADERSHIP_NAMES):
        return await interaction.response.send_message("Sem permissão.", ephemeral=True)

    if cargo not in membro.roles:
        return await interaction.response.send_message(
            "❌ O membro não possui esse cargo.",
            ephemeral=True
        )

    await membro.remove_roles(cargo, reason=f"Rebaixamento por {interaction.user}")
    await interaction.response.send_message(
        f"⬇️ {cargo.mention} removido de {membro.mention}.",
        ephemeral=True
    )

    await log(
        interaction.guild,
        "🎭・logs-cargos",
        "⬇️ Rebaixamento",
        f"{membro.mention} perdeu {cargo.mention}\nPor: {interaction.user.mention}"
    )


@bot.tree.command(name="ranking-farm", description="Mostra ranking de farm aprovado")
@app_commands.guild_only()
async def ranking_farm(interaction: discord.Interaction):
    conn = db()
    rows = conn.execute(
        """
        SELECT membro_id, SUM(quantidade) AS total
        FROM farms
        WHERE status='aprovado'
        GROUP BY membro_id
        ORDER BY total DESC
        LIMIT 10
        """
    ).fetchall()
    conn.close()

    if not rows:
        return await interaction.response.send_message(
            "Ainda não há farms aprovados.",
            ephemeral=True
        )

    lines = []
    for i, row in enumerate(rows, 1):
        lines.append(f"**{i}.** <@{row['membro_id']}> — **{row['total']}**")

    await interaction.response.send_message(
        "🏆 **Ranking de Farm**\n\n" + "\n".join(lines)
    )


@bot.tree.command(name="financeiro", description="Registra movimentação financeira")
@app_commands.describe(
    tipo="Ex.: venda, banco, lavagem, encomenda",
    valor="Valor",
    descricao="Descrição",
    membro="Membro relacionado"
)
@app_commands.guild_only()
async def financeiro(
    interaction: discord.Interaction,
    tipo: str,
    valor: float,
    descricao: str,
    membro: discord.Member | None = None
):
    if not has_any_role(interaction.user, LEADERSHIP_NAMES):
        return await interaction.response.send_message("Sem permissão.", ephemeral=True)

    conn = db()
    conn.execute(
        """
        INSERT INTO financeiro (tipo, membro_id, valor, descricao, autor_id, criado_em)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            tipo,
            membro.id if membro else None,
            valor,
            descricao,
            interaction.user.id,
            now()
        )
    )
    conn.commit()
    conn.close()

    await interaction.response.send_message(
        f"💰 Movimentação registrada: **{tipo} — R$ {valor:,.2f}**",
        ephemeral=True
    )

    await log(
        interaction.guild,
        "💰・logs-financeiro",
        "💰 Movimentação financeira",
        (
            f"**Tipo:** {tipo}\n"
            f"**Valor:** R$ {valor:,.2f}\n"
            f"**Membro:** {membro.mention if membro else '—'}\n"
            f"**Descrição:** {descricao}\n"
            f"**Registrado por:** {interaction.user.mention}"
        )
    )


@bot.tree.command(name="acao", description="Marca uma ação da facção")
@app_commands.describe(titulo="Nome da ação", horario="Data/horário", descricao="Detalhes")
@app_commands.guild_only()
async def acao(interaction: discord.Interaction, titulo: str, horario: str, descricao: str):
    if not has_any_role(interaction.user, ACTION_MANAGER_NAMES):
        return await interaction.response.send_message("Sem permissão.", ephemeral=True)

    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO acoes (titulo, horario, descricao, autor_id, criado_em)
        VALUES (?, ?, ?, ?, ?)
        """,
        (titulo, horario, descricao, interaction.user.id, now())
    )
    action_id = cur.lastrowid
    conn.commit()
    conn.close()

    channel = get_channel(interaction.guild, "📅・ações-marcadas")
    embed = discord.Embed(
        title=f"🎯 Ação #{action_id} • {titulo}",
        description=descricao
    )
    embed.add_field(name="Horário", value=horario, inline=False)
    embed.add_field(name="Responsável", value=interaction.user.mention, inline=False)

    await safe_send(channel, embed=embed)
    await interaction.response.send_message("✅ Ação marcada.", ephemeral=True)


@bot.tree.command(name="hierarquia", description="Mostra a hierarquia principal da facção")
@app_commands.guild_only()
async def hierarquia(interaction: discord.Interaction):
    order = [
        "👑 Dono",
        "👑 Sub-Dono",
        "⚜️ Gerente",
        "🔱 Líder",
        "🛡️ Sub-Líder",
        "💼 Gerente de Farm",
        "🎯 Gerente de Ação",
        "🔴 Membro",
        "🆕 Recruta"
    ]

    text = []
    for role_name in order:
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if role:
            text.append(f"{role.mention} — **{len(role.members)}** membro(s)")

    await interaction.response.send_message(
        "🎭 **Hierarquia da Facção**\n\n" + "\n".join(text)
    )


# =========================================================
# EVENTOS / LOGS
# =========================================================

@bot.event
async def on_member_join(member: discord.Member):
    visitor = discord.utils.get(member.guild.roles, name="👤 Visitante")
    if visitor:
        try:
            await member.add_roles(visitor, reason="Entrada automática")
        except discord.Forbidden:
            pass

    channel = get_channel(member.guild, "👋・boas-vindas")
    await safe_send(channel, f"👋 {member.mention} entrou no servidor. Faça seu registro no painel.")

    await log(
        member.guild,
        "👥・logs-membros",
        "➕ Membro entrou",
        f"{member.mention} entrou no servidor."
    )


@bot.event
async def on_member_remove(member: discord.Member):
    await log(
        member.guild,
        "👥・logs-membros",
        "➖ Membro saiu",
        f"**{member}** saiu do servidor."
    )


@bot.event
async def on_message_delete(message: discord.Message):
    if not message.guild or message.author.bot:
        return

    content = message.content or "*Sem conteúdo de texto*"
    await log(
        message.guild,
        "💬・logs-mensagens",
        "🗑️ Mensagem apagada",
        f"**Autor:** {message.author.mention}\n**Canal:** {message.channel.mention}\n**Conteúdo:** {content[:1500]}"
    )


@bot.event
async def on_ready():
    init_db()

    # Views persistentes
    bot.add_view(MainPanel())

    try:
        if GUILD_ID and GUILD_ID.isdigit():
            guild_obj = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild_obj)
            await bot.tree.sync(guild=guild_obj)
        else:
            await bot.tree.sync()

        print(f"Online como {bot.user}")

    except Exception as e:
        print("Erro sincronizando comandos:", e)
        traceback.print_exc()


bot.run(TOKEN)

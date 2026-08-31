import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

if not TOKEN:
    raise RuntimeError("Configure DISCORD_TOKEN no arquivo .env")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

ROLES = [
    ("👑 Dono", discord.Permissions(administrator=True)),
    ("👑 Sub-Dono", discord.Permissions(manage_guild=True, manage_channels=True, manage_roles=True, kick_members=True)),
    ("⚜️ Gerente", discord.Permissions(manage_messages=True, moderate_members=True)),
    ("🔱 Líder", discord.Permissions(manage_messages=True, moderate_members=True)),
    ("🛡️ Sub-Líder", discord.Permissions(manage_messages=True)),
    ("💼 Gerente de Farm", discord.Permissions(manage_messages=True)),
    ("🎯 Gerente de Ação", discord.Permissions(manage_messages=True)),
    ("🔴 Membro", discord.Permissions()),
    ("🆕 Recruta", discord.Permissions()),
    ("💤 Ausente", discord.Permissions()),
    ("🤝 Parceiro", discord.Permissions()),
    ("👤 Visitante", discord.Permissions()),
]

STRUCTURE = {
    "📌・INFORMAÇÕES": [
        ("📜・regras", "text"), ("📢・anúncios", "text"),
        ("📋・informações", "text"), ("🎭・hierarquia", "text"), ("🆘・suporte", "text")
    ],
    "🏘️・COMUNIDADE": [
        ("💬・chat-geral", "text"), ("📸・mídias", "text"),
        ("😂・resenha", "text"), ("💡・sugestões", "text"), ("🤖・comandos", "text")
    ],
    "📝・REGISTRO": [
        ("📝・registro", "text"), ("⏳・registros-pendentes", "text"),
        ("👤・visitantes", "text"), ("👋・boas-vindas", "text")
    ],
    "📦・FARM": [
        ("📦・painel-farm", "text"), ("⏳・aprovação-farm", "text"),
        ("🏆・ranking-farm", "text"), ("🎯・metas", "text"), ("📊・relatórios-farm", "text")
    ],
    "💰・GESTÃO": [
        ("📦・estoque", "text"), ("🔐・baú-liderança", "text"),
        ("🏦・banco", "text"), ("💵・vendas", "text"),
        ("📋・encomendas", "text"), ("💸・lavagem", "text"), ("📊・ranking-geral", "text")
    ],
    "🎯・AÇÕES": [
        ("📋・painel-ações", "text"), ("📅・ações-marcadas", "text"),
        ("📸・resultados", "text"), ("🏆・ranking-ações", "text")
    ],
    "💤・AUSÊNCIA": [
        ("📋・solicitar-ausência", "text"), ("⏳・aprovação-ausência", "text")
    ],
    "👑・LIDERANÇA": [
        ("💬・chat-liderança", "text"), ("👥・gerenciar-membros", "text"),
        ("⬆️・promoções-rebaixamentos", "text"), ("⚠️・advertências", "text"),
        ("📊・relatórios", "text"), ("📢・anúncio-privado", "text"),
        ("🎨・criador-de-embeds", "text"), ("💾・backups", "text")
    ],
    "🛡️・LOGS": [
        ("📑・logs-gerais", "text"), ("👥・logs-membros", "text"),
        ("💬・logs-mensagens", "text"), ("🔊・logs-voz", "text"),
        ("🎭・logs-cargos", "text"), ("💰・logs-financeiro", "text"),
        ("📦・logs-farm", "text"), ("🛡️・logs-segurança", "text")
    ],
    "🔊・CALLS": [
        ("🔊・Geral", "voice"), ("🔊・Resenha", "voice"), ("🔊・Farm", "voice"),
        ("🎯・Ação 01", "voice"), ("🎯・Ação 02", "voice"), ("🎯・Ação 03", "voice"),
        ("👑・Liderança", "voice"), ("💤・AFK", "voice")
    ],
}

PRIVATE_CATEGORIES = {"👑・LIDERANÇA", "🛡️・LOGS"}

async def get_or_create_role(guild, name, permissions):
    role = discord.utils.get(guild.roles, name=name)
    if role is None:
        role = await guild.create_role(name=name, permissions=permissions, reason="Setup Jorge Turco")
    return role

async def build_server(guild):
    roles = {}
    for name, perms in ROLES:
        roles[name] = await get_or_create_role(guild, name, perms)

    leadership = [roles[n] for n in ["👑 Dono", "👑 Sub-Dono", "⚜️ Gerente", "🔱 Líder", "🛡️ Sub-Líder"]]

    created = []
    for category_name, channels in STRUCTURE.items():
        category = discord.utils.get(guild.categories, name=category_name)
        if category is None:
            overwrites = None
            if category_name in PRIVATE_CATEGORIES:
                overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
                for role in leadership:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            category = await guild.create_category(category_name, overwrites=overwrites, reason="Setup Jorge Turco")
            created.append(category_name)

        for channel_name, kind in channels:
            existing = discord.utils.get(category.channels, name=channel_name)
            if existing:
                continue
            if kind == "voice":
                await guild.create_voice_channel(channel_name, category=category, reason="Setup Jorge Turco")
            else:
                await guild.create_text_channel(channel_name, category=category, reason="Setup Jorge Turco")
            created.append(channel_name)

    return created

class ConfirmSetup(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=60)
        self.author_id = author_id

    @discord.ui.button(label="Criar estrutura", style=discord.ButtonStyle.danger, emoji="🔴")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("Somente quem executou o comando pode confirmar.", ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Você precisa ser administrador.", ephemeral=True)

        await interaction.response.edit_message(content="Criando a estrutura da **JORGE TURCO**...", view=None)
        try:
            created = await build_server(interaction.guild)
            await interaction.followup.send(
                f"✅ Setup concluído. **{len(created)}** itens novos foram criados.\n"
                "Os canais de liderança e logs ficaram privados para os cargos de liderança.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ O bot não possui permissões suficientes para criar cargos/canais.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Erro durante o setup: `{type(e).__name__}`", ephemeral=True)

@bot.event
async def on_ready():
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

@bot.tree.command(name="setup-servidor", description="Cria a estrutura da Jorge Turco")
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def setup_servidor(interaction: discord.Interaction):
    embed = discord.Embed(
        title="JORGE TURCO • Setup do Servidor",
        description=(
            "Este setup criará os **cargos, categorias, canais, calls e áreas privadas** "
            "preparadas para o futuro Bot Facção Pro.\n\n"
            "Ele não apaga seus canais atuais e evita duplicar itens com o mesmo nome."
        )
    )
    embed.set_footer(text="Execute apenas em um servidor onde você tenha permissão.")
    await interaction.response.send_message(embed=embed, view=ConfirmSetup(interaction.user.id), ephemeral=True)

bot.run(TOKEN)

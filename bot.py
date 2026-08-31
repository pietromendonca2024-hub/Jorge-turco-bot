import os
import asyncio
import traceback
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
    ("👑 Sub-Dono", discord.Permissions(
        manage_guild=True,
        manage_channels=True,
        manage_roles=True,
        kick_members=True
    )),
    ("⚜️ Gerente", discord.Permissions(
        manage_messages=True,
        moderate_members=True
    )),
    ("🔱 Líder", discord.Permissions(
        manage_messages=True,
        moderate_members=True
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

PRIVATE_CATEGORIES = {"👑・LIDERANÇA", "🛡️・LOGS"}


async def get_or_create_role(guild: discord.Guild, name: str, permissions: discord.Permissions):
    role = discord.utils.get(guild.roles, name=name)

    if role is None:
        role = await guild.create_role(
            name=name,
            permissions=permissions,
            reason="Setup Jorge Turco"
        )

    return role


async def wipe_server(guild: discord.Guild):
    """
    Apaga canais/categorias e cargos deletáveis do servidor.

    Não é possível apagar:
    - @everyone
    - cargos gerenciados por bots/integrações
    - o próprio cargo gerenciado do bot
    - cargos acima do cargo mais alto do bot
    """
    removed_channels = 0
    removed_roles = 0
    skipped_roles = []

    # Apaga canais primeiro. Categorias desaparecem quando apagadas explicitamente
    # depois, caso ainda existam.
    for channel in list(guild.channels):
        try:
            await channel.delete(reason="Reset completo Jorge Turco")
            removed_channels += 1
            await asyncio.sleep(0.15)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # Atualiza cache básico após as exclusões.
    await asyncio.sleep(1)

    me = guild.me
    bot_top_role = me.top_role if me else None

    # Do cargo mais alto para o mais baixo.
    for role in sorted(guild.roles, key=lambda r: r.position, reverse=True):
        if role.is_default():
            continue

        if role.managed:
            skipped_roles.append(role.name)
            continue

        if bot_top_role is not None and role >= bot_top_role:
            skipped_roles.append(role.name)
            continue

        try:
            await role.delete(reason="Reset completo Jorge Turco")
            removed_roles += 1
            await asyncio.sleep(0.15)
        except (discord.Forbidden, discord.HTTPException):
            skipped_roles.append(role.name)

    return removed_channels, removed_roles, skipped_roles


async def build_server(guild: discord.Guild):
    roles = {}

    for name, perms in ROLES:
        roles[name] = await get_or_create_role(guild, name, perms)

    leadership = [
        roles[n]
        for n in [
            "👑 Dono",
            "👑 Sub-Dono",
            "⚜️ Gerente",
            "🔱 Líder",
            "🛡️ Sub-Líder",
        ]
    ]

    created = []

    for category_name, channels in STRUCTURE.items():
        category = discord.utils.get(guild.categories, name=category_name)

        if category is None:
            # Não passa overwrites=None. Em algumas versões isso pode causar TypeError.
            if category_name in PRIVATE_CATEGORIES:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        view_channel=False
                    )
                }

                for role in leadership:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                    )

                category = await guild.create_category(
                    category_name,
                    overwrites=overwrites,
                    reason="Setup Jorge Turco"
                )
            else:
                category = await guild.create_category(
                    category_name,
                    reason="Setup Jorge Turco"
                )

            created.append(category_name)

        for channel_name, kind in channels:
            existing = discord.utils.get(category.channels, name=channel_name)

            if existing:
                continue

            if kind == "voice":
                await guild.create_voice_channel(
                    channel_name,
                    category=category,
                    reason="Setup Jorge Turco"
                )
            else:
                await guild.create_text_channel(
                    channel_name,
                    category=category,
                    reason="Setup Jorge Turco"
                )

            created.append(channel_name)

    return created


class ConfirmSetup(discord.ui.View):
    def __init__(self, author_id: int, full_reset: bool = False):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.full_reset = full_reset

    @discord.ui.button(
        label="CONFIRMAR",
        style=discord.ButtonStyle.danger,
        emoji="⚠️"
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message(
                "Somente quem executou o comando pode confirmar.",
                ephemeral=True
            )

        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "Você precisa ser administrador.",
                ephemeral=True
            )

        guild = interaction.guild

        if guild is None:
            return await interaction.response.send_message(
                "Este comando só funciona dentro de um servidor.",
                ephemeral=True
            )

        # Responde antes de apagar os canais, pois o canal atual pode ser deletado.
        if self.full_reset:
            await interaction.response.edit_message(
                content=(
                    "⚠️ **RESET INICIADO.**\n"
                    "Os canais e cargos deletáveis serão apagados e a estrutura será criada do zero.\n"
                    "A mensagem pode desaparecer quando este canal for excluído."
                ),
                embed=None,
                view=None
            )
        else:
            await interaction.response.edit_message(
                content="Criando a estrutura da **JORGE TURCO**...",
                embed=None,
                view=None
            )

        try:
            removed_channels = 0
            removed_roles = 0
            skipped_roles = []

            if self.full_reset:
                removed_channels, removed_roles, skipped_roles = await wipe_server(guild)

            created = await build_server(guild)

            # Como o canal original pode ter sido apagado, manda o resultado
            # no novo canal de comandos ou no chat-geral.
            target = discord.utils.get(guild.text_channels, name="🤖・comandos")
            if target is None:
                target = discord.utils.get(guild.text_channels, name="💬・chat-geral")

            if target is not None:
                text = (
                    "✅ **SETUP CONCLUÍDO!**\n"
                    f"• Canais/categorias removidos: **{removed_channels}**\n"
                    f"• Cargos removidos: **{removed_roles}**\n"
                    f"• Itens criados: **{len(created)}**"
                )

                if skipped_roles:
                    text += (
                        "\n\n⚠️ Alguns cargos não puderam ser apagados "
                        "porque são gerenciados ou estão acima do cargo do bot:\n"
                        + ", ".join(skipped_roles[:15])
                    )

                await target.send(text)

        except discord.Forbidden:
            traceback.print_exc()

            target = discord.utils.get(guild.text_channels, name="🤖・comandos")
            if target:
                await target.send(
                    "❌ O bot não possui permissões suficientes. "
                    "Dê **Administrador** ao bot e coloque o cargo dele acima dos cargos que deseja apagar/criar."
                )

        except Exception as e:
            traceback.print_exc()

            target = discord.utils.get(guild.text_channels, name="🤖・comandos")
            if target:
                await target.send(
                    f"❌ Erro durante o setup:\n```{type(e).__name__}: {e}```"
                )


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
        traceback.print_exc()


@bot.tree.command(
    name="setup-servidor",
    description="Cria a estrutura da Jorge Turco sem apagar o servidor"
)
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def setup_servidor(interaction: discord.Interaction):
    embed = discord.Embed(
        title="JORGE TURCO • Setup do Servidor",
        description=(
            "Este modo cria os **cargos, categorias, canais, calls e áreas privadas** "
            "sem apagar o que já existe.\n\n"
            "Use `/reset-servidor` se quiser apagar os canais e cargos deletáveis "
            "e montar tudo do zero."
        )
    )

    embed.set_footer(
        text="Execute apenas em um servidor onde você tenha permissão."
    )

    await interaction.response.send_message(
        embed=embed,
        view=ConfirmSetup(interaction.user.id, full_reset=False),
        ephemeral=True
    )


@bot.tree.command(
    name="reset-servidor",
    description="APAGA canais/cargos deletáveis e recria a Jorge Turco do zero"
)
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def reset_servidor(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚠️ JORGE TURCO • RESET COMPLETO",
        description=(
            "**ATENÇÃO: ESTA AÇÃO É DESTRUTIVA.**\n\n"
            "Ao confirmar, o bot tentará apagar:\n"
            "• todos os canais e categorias;\n"
            "• todos os cargos que ele tiver permissão para excluir;\n\n"
            "Depois, criará toda a estrutura da JORGE TURCO do zero.\n\n"
            "**Não há desfazer automático.**"
        ),
        color=discord.Color.red()
    )

    embed.set_footer(
        text="O @everyone e cargos gerenciados por bots/integrações não podem ser apagados."
    )

    await interaction.response.send_message(
        embed=embed,
        view=ConfirmSetup(interaction.user.id, full_reset=True),
        ephemeral=True
    )


bot.run(TOKEN)

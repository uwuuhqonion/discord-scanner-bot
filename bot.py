import asyncio
import random
import string
import discord
from discord import app_commands
import requests

# --- CONFIGURATION ---
BOT_TOKEN = "MTU1Mzc2MjU3NDQzOTQxNTgzOA.GKB6kf.Ojj8KgZyNHIG4Vw7OGGIi11JG0X5zbCNfL-Fe4"

# Tes 5 tokens en rotation
USER_TOKENS = [
    "MTU1MzU3OTc1OTQ1ODQ1NTY1NQ.G1ZWU1.MAxriPkxsR29eya06JbJKSBKvkXkbComeYdNK8",
    "ODA1MDQyOTg2MTg2MTc4NTgw.GKvOeX.kYoS-GgSuM8MFE6Bq7ZCzFvwzUUBW3BtrENwzc",
    "ODA1MDQyOTg2MTg2MTc4NTgw.GcQzYA.9NQ6BJ7PbAKoq5wWEe2FHrl8s0vjIherwNKX9E",
    "MTQ1ODUyNjc4MTg1NzQ2ODY3MA.G_0Q4M.3MW6XE9q11hufWLhPhp9Rr7t4LAKPRWcaE67_c",
    "MTU1MzQyMTY4MTU1MTQ3ODg1Ng.GH6dMO.esOUFU8pq5U9LFUdmzLO9c7dqtVSLSkHH_nQXI"
]

# Remplace par tes vrais IDs de salons et de serveur
CHANNEL_CMD_ID = 1553580588772892693          # ID de ton salon #cmd
CHANNEL_LIBRE_ID = 1553438956895469681        # ID de ton salon #pseudo-libre
CHANNEL_PRIS_ID = 1554575275176632350         # ID de ton salon #pseudo-non-dispo
MY_SERVER_ID = 1553438955855151164            # ID de ton serveur Discord

active_tasks = 0
MAX_CONCURRENT_TASKS = 3
scan_active = True
DICTIONARY_WORDS = []

class CompleteSearchBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = False
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        global DICTIONARY_WORDS
        print("📚 Chargement du dictionnaire français...")
        try:
            response = requests.get("https://raw.githubusercontent.com/Taknok/French-Wordlist/master/francais.txt")
            if response.status_code == 200:
                DICTIONARY_WORDS = [word.strip().lower() for word in response.text.splitlines() if 3 <= len(word.strip()) <= 15 and word.strip().isalpha()]
                print(f"✅ {len(DICTIONARY_WORDS)} mots chargés dans le dictionnaire avec succès !")
            else:
                DICTIONARY_WORDS = ["chat", "chien", "lune", "soleil", "table", "chaise"]
        except Exception:
            DICTIONARY_WORDS = ["chat", "chien", "lune", "soleil"]

        # Synchronisation propre et directe sur ton serveur
        MY_GUILD = discord.Object(id=MY_SERVER_ID)
        self.tree.clear_commands(guild=MY_GUILD)
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        print(f"🤖 Commandes synchronisées avec succès pour {self.user}")

client = CompleteSearchBot()

# --- FONCTIONS DE TEST API ---
def tester_pseudo(username, token):
    url = "https://discord.com/api/v9/users/@me/pomelo-attempt"
    headers = {
        "Authorization": token.strip(),
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.post(url, json={"username": username}, headers=headers, timeout=3)
        if response.status_code in [401, 403]:
            return "FLAGGED"
        if response.status_code == 200:
            return response.json().get("taken", True)
    except Exception:
        pass
    return True

def tester_url(code, token):
    url = f"https://discord.com/api/v9/invites/{code}"
    headers = {
        "Authorization": token.strip(),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=3)
        if response.status_code in [401, 403]:
            return "FLAGGED"
        if response.status_code == 404:
            return False  # 404 = L'invitation n'existe pas, donc potentiellement dispo
        elif response.status_code == 200:
            return True   # 200 = L'invitation existe (prise)
    except Exception:
        pass
    return True

async def check_permissions_and_limit(interaction: discord.Interaction):
    global active_tasks
    if interaction.channel.id != CHANNEL_CMD_ID:
        await interaction.response.send_message("❌ Ces commandes ne peuvent être utilisées que dans le salon textuel **#cmd** désigné !", ephemeral=True)
        return False
        
    if active_tasks >= MAX_CONCURRENT_TASKS:
        await interaction.response.send_message(f"⚠️ Le bot est déjà au maximum de ses capacités ({active_tasks}/{MAX_CONCURRENT_TASKS} tâches). Veuillez patienter ou utiliser `/stop` !", ephemeral=True)
        return False
    return True

# --- INTERFACE INTERACTIVE POUR /url ---
class UrlSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.select(
        placeholder="🌐 Choisis le type d'URL Discord à scanner...",
        options=[
            discord.SelectOption(label="2 Caractères", value="2c", description="Ex: a1, 9z..."),
            discord.SelectOption(label="2 Lettres", value="2l", description="Ex: ab, xy..."),
            discord.SelectOption(label="3 Lettres", value="3l", description="Ex: abc, xyz..."),
            discord.SelectOption(label="4 Lettres", value="4l", description="Ex: abcd, test..."),
            discord.SelectOption(label="Dictionnaire (Meaning)", value="meaning", description="Vérifie de vrais mots français"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        global scan_active
        scan_active = True
        choice = select.values[0]

        if choice == "2c":
            await interaction.response.send_message("🌐 Scan des URLs **2 Caractères** (`discord.gg/xx`) lancé en arrière-plan !", ephemeral=True)
            asyncio.create_task(run_url_scan_task(interaction, string.ascii_lowercase + string.digits, 2, "URL 2 Caractères"))
        elif choice == "2l":
            await interaction.response.send_message("🌐 Scan des URLs **2 Lettres** (`discord.gg/xx`) lancé en arrière-plan !", ephemeral=True)
            asyncio.create_task(run_url_scan_task(interaction, string.ascii_lowercase, 2, "URL 2 Lettres"))
        elif choice == "3l":
            await interaction.response.send_message("🌐 Scan des URLs **3 Lettres** (`discord.gg/xxx`) lancé en arrière-plan !", ephemeral=True)
            asyncio.create_task(run_url_scan_task(interaction, string.ascii_lowercase, 3, "URL 3 Lettres"))
        elif choice == "4l":
            await interaction.response.send_message("🌐 Scan des URLs **4 Lettres** (`discord.gg/xxxx`) lancé en arrière-plan !", ephemeral=True)
            asyncio.create_task(run_url_scan_task(interaction, string.ascii_lowercase, 4, "URL 4 Lettres"))
        elif choice == "meaning":
            await interaction.response.send_message("🌐 Scan des URLs **Dictionnaire** (`discord.gg/mot`) lancé en arrière-plan !", ephemeral=True)
            asyncio.create_task(run_url_dictionary_task(interaction))

# --- TÂCHES DE SCAN D'URLS ---
async def run_url_scan_task(interaction: discord.Interaction, charset, length, label):
    global active_tasks, scan_active
    active_tasks += 1
    guild = interaction.guild
    channel_cmd = guild.get_channel(CHANNEL_CMD_ID)
    channel_libre = guild.get_channel(CHANNEL_LIBRE_ID)
    channel_pris = guild.get_channel(CHANNEL_PRIS_ID)
    
    token_index = 0
    deja_testes = set()
    
    try:
        while scan_active:
            code = ''.join(random.choices(charset, k=length))
            if code in deja_testes:
                continue
            deja_testes.add(code)
            
            token_actuel = USER_TOKENS[token_index]
            resultat = await asyncio.to_thread(tester_url, code, token_actuel)
            
            if not scan_active:
                break

            if resultat == "FLAGGED":
                if channel_cmd:
                    await channel_cmd.send(f"🚨 **ALERTE** : Le **Token n°{token_index + 1}** s'est fait flag/bannir pendant le scan **{label}** !")
            elif not resultat:  # False = Disponible (404)
                if channel_libre:
                    await channel_libre.send(f"@everyone 🌐🎉 **URL DISPONIBLE ({label})** : `discord.gg/{code}`")
            else:  # True = Pris
                if channel_pris:
                    await channel_pris.send(f"❌ **URL PRIS ({label})** : `discord.gg/{code}`")
            
            token_index = (token_index + 1) % len(USER_TOKENS)
            await asyncio.sleep(random.uniform(3, 5))
    finally:
        active_tasks = max(0, active_tasks - 1)

async def run_url_dictionary_task(interaction: discord.Interaction):
    global active_tasks, scan_active, DICTIONARY_WORDS
    active_tasks += 1
    guild = interaction.guild
    channel_cmd = guild.get_channel(CHANNEL_CMD_ID)
    channel_libre = guild.get_channel(CHANNEL_LIBRE_ID)
    channel_pris = guild.get_channel(CHANNEL_PRIS_ID)
    
    token_index = 0
    deja_testes = set()
    
    try:
        mots = list(DICTIONARY_WORDS)
        random.shuffle(mots)
        for code in mots:
            if not scan_active:
                break
            if code in deja_testes:
                continue
            deja_testes.add(code)
            
            token_actuel = USER_TOKENS[token_index]
            resultat = await asyncio.to_thread(tester_url, code, token_actuel)
            
            if not scan_active:
                break

            if resultat == "FLAGGED":
                if channel_cmd:
                    await channel_cmd.send(f"🚨 **ALERTE** : Le **Token n°{token_index + 1}** s'est fait flag/bannir pendant le scan URL Dictionnaire !")
            elif not resultat:
                if channel_libre:
                    await channel_libre.send(f"@everyone 🌐🎉 **URL DISPONIBLE (Dictionnaire)** : `discord.gg/{code}`")
            else:
                if channel_pris:
                    await channel_pris.send(f"❌ **URL PRIS (Dictionnaire)** : `discord.gg/{code}`")
            
            token_index = (token_index + 1) % len(USER_TOKENS)
            await asyncio.sleep(random.uniform(3, 5))
    finally:
        active_tasks = max(0, active_tasks - 1)

# --- COMMANDES SLASH CLASSIQUES ---
@client.tree.command(name="url", description="Ouvre l'interface de scan des liens d'invitation Discord.")
async def url_menu(interaction: discord.Interaction):
    if not await check_permissions_and_limit(interaction):
        return
    view = UrlSelectView()
    await interaction.response.send_message("🎛️ **Panneau de contrôle des URLs Discord**\nSélectionne le type de lien que tu souhaites scanner dans le menu ci-dessous :", view=view, ephemeral=True)

@client.tree.command(name="search", description="Vérifie si un pseudo précis est disponible.")
@app_commands.describe(username="Le pseudo à tester")
async def search(interaction: discord.Interaction, username: str):
    if not await check_permissions_and_limit(interaction):
        return
        
    await interaction.response.defer(thinking=True)
    token = USER_TOKENS[0]
    resultat = await asyncio.to_thread(tester_pseudo, username, token)
    
    if resultat == "FLAGGED":
        await interaction.followup.send(f"🚨 **ALERTE TOKEN** : Le token 1 s'est fait flag / bloquer par l'API !")
        return

    guild = interaction.guild
    channel_libre = guild.get_channel(CHANNEL_LIBRE_ID)
    channel_pris = guild.get_channel(CHANNEL_PRIS_ID)

    if not resultat:
        await interaction.followup.send(f"✅ Le pseudo **`{username}`** est **DISPONIBLE** !")
        if channel_libre:
            await channel_libre.send(f"✅ **DISPONIBLE** : `{username}` (Trouvé via `/search` par {interaction.user.mention})")
    else:
        await interaction.followup.send(f"❌ Le pseudo **`{username}`** est déjà **PRIS**.")
        if channel_pris:
            await channel_pris.send(f"❌ **PRIS** : `{username}`")

async def run_dictionary_scan(interaction: discord.Interaction):
    global active_tasks, scan_active, DICTIONARY_WORDS
    if not await check_permissions_and_limit(interaction):
        return

    if not DICTIONARY_WORDS:
        await interaction.response.send_message("❌ Le dictionnaire n'est pas chargé.", ephemeral=True)
        return

    active_tasks += 1
    await interaction.response.send_message(f"📖 Scan aléatoire des **mots du dictionnaire** (pseudos) lancé ! (`{active_tasks}/{MAX_CONCURRENT_TASKS}` tâches)", ephemeral=True)
    
    guild = interaction.guild
    channel_cmd = guild.get_channel(CHANNEL_CMD_ID)
    channel_libre = guild.get_channel(CHANNEL_LIBRE_ID)
    channel_pris = guild.get_channel(CHANNEL_PRIS_ID)
    
    token_index = 0
    deja_testes = set()
    
    try:
        mots_aleatoires = list(DICTIONARY_WORDS)
        random.shuffle(mots_aleatoires)
        
        for pseudo in mots_aleatoires:
            if not scan_active:
                break
            if pseudo in deja_testes:
                continue
            deja_testes.add(pseudo)
            
            token_actuel = USER_TOKENS[token_index]
            resultat = await asyncio.to_thread(tester_pseudo, pseudo, token_actuel)
            
            if not scan_active:
                break

            if resultat == "FLAGGED":
                if channel_cmd:
                    await channel_cmd.send(f"🚨 **ALERTE** : Le **Token n°{token_index + 1}** s'est fait flag pendant le scan dictionnaire !")
            elif not resultat:
                if channel_libre:
                    await channel_libre.send(f"@everyone 🎉 **DISPONIBLE (Dictionnaire)** : `{pseudo}`")
            else:
                if channel_pris:
                    await channel_pris.send(f"❌ **PRIS (Dictionnaire)** : `{pseudo}`")
            
            token_index = (token_index + 1) % len(USER_TOKENS)
            await asyncio.sleep(random.uniform(3, 5))
    finally:
        active_tasks = max(0, active_tasks - 1)

@client.tree.command(name="meaning", description="Scanne aléatoirement de vrais mots du dictionnaire français (Pseudos).")
async def scan_meaning(interaction: discord.Interaction):
    global scan_active
    scan_active = True
    await run_dictionary_scan(interaction)

@client.tree.command(name="status", description="Affiche le nombre de scans en cours et l'état du bot.")
async def status_cmd(interaction: discord.Interaction):
    if interaction.channel.id != CHANNEL_CMD_ID:
        await interaction.response.send_message("❌ Cette commande ne peut être utilisée que dans le salon **#cmd** !", ephemeral=True)
        return
    await interaction.response.send_message(f"📊 **Statut du Bot** :\n- Scans en cours : `{active_tasks} / {MAX_CONCURRENT_TASKS}`\n- Statut global : `{'Actif' if scan_active else 'Arrêté'}`", ephemeral=True)

@client.tree.command(name="stop", description="Arrête tous les scans en cours.")
async def stop_scans(interaction: discord.Interaction):
    global scan_active, active_tasks
    if interaction.channel.id != CHANNEL_CMD_ID:
        await interaction.response.send_message("❌ Cette commande ne peut être utilisée que dans le salon **#cmd** !", ephemeral=True)
        return
    scan_active = False
    active_tasks = 0
    await interaction.response.send_message("🛑 **Tous les scans en cours ont été interrompus avec succès.**")

async def run_random_scan(interaction: discord.Interaction, charset, length, label, allow_special=False):
    global active_tasks, scan_active
    if not await check_permissions_and_limit(interaction):
        return

    active_tasks += 1
    await interaction.response.send_message(f"🔍 Scan aléatoire des pseudos **{label}** lancé ! (`{active_tasks}/{MAX_CONCURRENT_TASKS}` tâches)", ephemeral=True)
    
    guild = interaction.guild
    channel_cmd = guild.get_channel(CHANNEL_CMD_ID)
    channel_libre = guild.get_channel(CHANNEL_LIBRE_ID)
    channel_pris = guild.get_channel(CHANNEL_PRIS_ID)
    
    token_index = 0
    deja_testes = set()
    
    try:
        while scan_active:
            if allow_special:
                base_chars = ''.join(random.choices(charset, k=3))
                special_char = random.choice(['.', '_'])
                pos = random.randint(0, 3)
                pseudo = base_chars[:pos] + special_char + base_chars[pos:]
            else:
                pseudo = ''.join(random.choices(charset, k=length))

            if pseudo in deja_testes:
                continue
            deja_testes.add(pseudo)
            
            token_actuel = USER_TOKENS[token_index]
            resultat = await asyncio.to_thread(tester_pseudo, pseudo, token_actuel)
            
            if not scan_active:
                break

            if resultat == "FLAGGED":
                if channel_cmd:
                    await channel_cmd.send(f"🚨 **ALERTE** : Le **Token n°{token_index + 1}** s'est fait flag pendant le scan **{label}** !")
            elif not resultat:
                if channel_libre:
                    await channel_libre.send(f"@everyone 🎉 **DISPONIBLE ({label})** : `{pseudo}`")
            else:
                if channel_pris:
                    await channel_pris.send(f"❌ **PRIS ({label})** : `{pseudo}`")
            
            token_index = (token_index + 1) % len(USER_TOKENS)
            await asyncio.sleep(random.uniform(3, 5))
    finally:
        active_tasks = max(0, active_tasks - 1)

@client.tree.command(name="3c", description="Scanne aléatoirement les pseudos à 3 caractères.")
async def scan_3c(interaction: discord.Interaction):
    global scan_active
    scan_active = True
    await run_random_scan(interaction, string.ascii_lowercase + string.digits, 3, "3 Caractères")

@client.tree.command(name="4c", description="Scanne aléatoirement les pseudos à 4 caractères.")
async def scan_4c(interaction: discord.Interaction):
    global scan_active
    scan_active = True
    await run_random_scan(interaction, string.ascii_lowercase + string.digits, 4, "4 Caractères")

@client.tree.command(name="3l", description="Scanne aléatoirement les pseudos à 3 lettres.")
async def scan_3l(interaction: discord.Interaction):
    global scan_active
    scan_active = True
    await run_random_scan(interaction, string.ascii_lowercase, 3, "3 Lettres")

@client.tree.command(name="4l", description="Scanne aléatoirement les pseudos à 4 lettres.")
async def scan_4l(interaction: discord.Interaction):
    global scan_active
    scan_active = True
    await run_random_scan(interaction, string.ascii_lowercase, 4, "4 Lettres")

@client.tree.command(name="semi", description="Scanne des pseudos semi-clean à 4 caractères incluant un . ou _")
async def scan_semi(interaction: discord.Interaction):
    global scan_active
    scan_active = True
    await run_random_scan(interaction, string.ascii_lowercase + string.digits, 4, "Semi-Clean (. ou _)", allow_special=True)

client.run(BOT_TOKEN)
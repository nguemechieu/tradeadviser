import re


DEFAULT_LANGUAGE = "en"

SUPPORTED_LANGUAGES = {
    "en": "English",
    "fr": "Francais",
    "es": "Espanol",
    "pt": "Portugues",
}


TRANSLATIONS = {
    "app.window_title": {
        "en": "TradeAdviser",
        "fr": "TradeAdviser",
        "es": "TradeAdviser",
        "pt": "TradeAdviser",
    },
    "dashboard.window_title": {
        "en": "TradeAdviser",
        "fr": "TradeAdviser",
        "es": "TradeAdviser",
        "pt": "TradeAdviser",
    },
    "dashboard.hero_eyebrow": {
        "en": "AI Trading Command Deck",
        "fr": "Poste de Commande Trading IA",
        "es": "Centro de Mando de Trading IA",
        "pt": "Central de Comando de Trading IA",
    },
    "dashboard.hero_title": {
        "en": "TradeAdviser",
        "fr": "TradeAdviser",
        "es": "TradeAdviser",
        "pt": "TradeAdviser",
    },
    "dashboard.hero_lead": {
        "en": "Configure broker access and risk profile before launching the trading terminal.",
        "fr": "Configurez l'acces broker et le profil de risque avant d'ouvrir le terminal.",
        "es": "Configura el acceso al broker y el perfil de riesgo antes de abrir el terminal.",
        "pt": "Configure o acesso da corretora e o perfil de risco antes de abrir o terminal.",
    },
    "dashboard.connect_title": {
        "en": "Connect Your Desk",
        "fr": "Connectez Votre Desk",
        "es": "Conecta Tu Desk",
        "pt": "Conecte Sua Mesa",
    },
    "dashboard.connect_body": {
        "en": "Choose a session preset, tune the account details, and launch into the terminal with a cleaner pre-trade summary.",
        "fr": "Choisissez un preset, ajustez le compte et ouvrez le terminal avec un resume pre-trade plus clair.",
        "es": "Elige un preset, ajusta la cuenta y abre el terminal con un resumen pre-trade mas claro.",
        "pt": "Escolha um preset, ajuste a conta e abra o terminal com um resumo pre-trade mais claro.",
    },
    "dashboard.quick_presets": {
        "en": "Quick Presets",
        "fr": "Presets Rapides",
        "es": "Presets Rapidos",
        "pt": "Presets Rapidos",
    },
    "dashboard.paper_preset": {
        "en": "Paper Warmup",
        "fr": "Echauffement Paper",
        "es": "Inicio Paper",
        "pt": "Aquecimento Paper",
    },
    "dashboard.crypto_preset": {
        "en": "Crypto Live",
        "fr": "Crypto Live",
        "es": "Crypto Live",
        "pt": "Crypto Live",
    },
    "dashboard.fx_preset": {
        "en": "FX Live",
        "fr": "FX Live",
        "es": "FX Live",
        "pt": "FX Live",
    },
    "dashboard.desk_snapshot_title": {
        "en": "Desk Snapshot",
        "fr": "Vue du Desk",
        "es": "Resumen del Desk",
        "pt": "Resumo da Mesa",
    },
    "dashboard.desk_snapshot_body": {
        "en": "Use the dashboard like a pre-flight panel: confirm broker type, credentials, and risk posture before the terminal takes over.",
        "fr": "Utilisez ce tableau de bord comme un panneau de verification: confirmez le type de broker, les identifiants et le risque avant le terminal.",
        "es": "Usa este panel como verificacion previa: confirma el broker, las credenciales y el riesgo antes del terminal.",
        "pt": "Use este painel como verificacao previa: confirme corretora, credenciais e risco antes do terminal.",
    },
    "dashboard.market_primary_title": {
        "en": "Primary Venue",
        "fr": "Place Principale",
        "es": "Mercado Principal",
        "pt": "Mercado Principal",
    },
    "dashboard.market_secondary_title": {
        "en": "Strategy Lens",
        "fr": "Vue Strategie",
        "es": "Enfoque de Estrategia",
        "pt": "Visao da Estrategia",
    },
    "dashboard.market_tertiary_title": {
        "en": "Operator Signal",
        "fr": "Signal Operateur",
        "es": "Senal Operativa",
        "pt": "Sinal Operacional",
    },
    "dashboard.launch_checklist_title": {
        "en": "Launch Checklist",
        "fr": "Checklist de Lancement",
        "es": "Lista de Lanzamiento",
        "pt": "Checklist de Inicializacao",
    },
    "dashboard.check_credentials_title": {
        "en": "Credentials",
        "fr": "Identifiants",
        "es": "Credenciales",
        "pt": "Credenciais",
    },
    "dashboard.check_broker_title": {
        "en": "Broker setup",
        "fr": "Configuration broker",
        "es": "Configuracion del broker",
        "pt": "Configuracao do broker",
    },
    "dashboard.check_strategy_title": {
        "en": "Strategy routing",
        "fr": "Routage strategie",
        "es": "Enrutamiento de estrategia",
        "pt": "Roteamento de estrategia",
    },
    "dashboard.check_risk_title": {
        "en": "Risk profile",
        "fr": "Profil de risque",
        "es": "Perfil de riesgo",
        "pt": "Perfil de risco",
    },
    "dashboard.notes_title": {
        "en": "Session Notes",
        "fr": "Notes de Session",
        "es": "Notas de Sesion",
        "pt": "Notas da Sessao",
    },
    "dashboard.notes_bullet_1": {
        "en": "Paper mode is the safest way to verify broker setup and chart loading.",
        "fr": "Le mode paper est le moyen le plus sur de verifier le broker et les graphiques.",
        "es": "El modo paper es la forma mas segura de verificar broker y graficos.",
        "pt": "O modo paper e a forma mais segura de verificar corretora e graficos.",
    },
    "dashboard.notes_bullet_2": {
        "en": "Broker-specific fields appear only when the selected venue requires them.",
        "fr": "Les champs specifiques n'apparaissent que si le broker les exige.",
        "es": "Los campos especificos solo aparecen cuando el broker los requiere.",
        "pt": "Os campos especificos so aparecem quando a corretora exige.",
    },
    "dashboard.notes_bullet_3": {
        "en": "Saved profiles help repeat sessions start faster.",
        "fr": "Les profils enregistres accelerent les sessions suivantes.",
        "es": "Los perfiles guardados aceleran las siguientes sesiones.",
        "pt": "Os perfis salvos aceleram as proximas sessoes.",
    },
    "dashboard.notes_bullet_4": {
        "en": "Live sessions should be reviewed carefully before launch.",
        "fr": "Les sessions live doivent etre verifiees avec soin avant lancement.",
        "es": "Las sesiones live deben revisarse con cuidado antes del inicio.",
        "pt": "As sessoes live devem ser revisadas com cuidado antes do inicio.",
    },
    "dashboard.saved_profiles": {
        "en": "Saved Profiles",
        "fr": "Profils Enregistres",
        "es": "Perfiles Guardados",
        "pt": "Perfis Salvos",
    },
    "dashboard.recent_profiles": {
        "en": "Recent profiles",
        "fr": "Profils recents",
        "es": "Perfiles recientes",
        "pt": "Perfis recentes",
    },
    "dashboard.choose_profile": {
        "en": "Choose Profile",
        "fr": "Choisir un Profil",
        "es": "Elegir Perfil",
        "pt": "Escolher Perfil",
    },
    "dashboard.refresh": {
        "en": "Refresh",
        "fr": "Actualiser",
        "es": "Actualizar",
        "pt": "Atualizar",
    },
    "dashboard.market_access": {
        "en": "Market Access",
        "fr": "Acces Marche",
        "es": "Acceso al Mercado",
        "pt": "Acesso ao Mercado",
    },
    "dashboard.broker_type": {
        "en": "Broker Type",
        "fr": "Type de Broker",
        "es": "Tipo de Broker",
        "pt": "Tipo de Broker",
    },
    "dashboard.exchange": {
        "en": "Exchange",
        "fr": "Exchange",
        "es": "Exchange",
        "pt": "Exchange",
    },
    "dashboard.mode": {
        "en": "Mode",
        "fr": "Mode",
        "es": "Modo",
        "pt": "Modo",
    },
    "dashboard.strategy": {
        "en": "Strategy",
        "fr": "Strategie",
        "es": "Estrategia",
        "pt": "Estrategia",
    },
    "dashboard.credentials": {
        "en": "Credentials",
        "fr": "Identifiants",
        "es": "Credenciales",
        "pt": "Credenciais",
    },
    "dashboard.api_key": {
        "en": "API Key",
        "fr": "Cle API",
        "es": "Clave API",
        "pt": "Chave API",
    },
    "dashboard.secret": {
        "en": "Secret",
        "fr": "Secret",
        "es": "Secreto",
        "pt": "Segredo",
    },
    "dashboard.passphrase": {
        "en": "Passphrase",
        "fr": "Phrase Secrete",
        "es": "Frase Secreta",
        "pt": "Frase Secreta",
    },
    "dashboard.account_id": {
        "en": "Account ID",
        "fr": "ID Compte",
        "es": "ID de Cuenta",
        "pt": "ID da Conta",
    },
    "dashboard.language": {
        "en": "Language",
        "fr": "Langue",
        "es": "Idioma",
        "pt": "Idioma",
    },
    "dashboard.risk_persistence": {
        "en": "Risk and Persistence",
        "fr": "Risque et Sauvegarde",
        "es": "Riesgo y Guardado",
        "pt": "Risco e Persistencia",
    },
    "dashboard.risk_budget": {
        "en": "Risk Budget",
        "fr": "Budget Risque",
        "es": "Presupuesto de Riesgo",
        "pt": "Orcamento de Risco",
    },
    "dashboard.save_profile": {
        "en": "Save this broker profile",
        "fr": "Enregistrer ce profil broker",
        "es": "Guardar este perfil de broker",
        "pt": "Salvar este perfil de broker",
    },
    "dashboard.connect_paper": {
        "en": "Open Paper Terminal",
        "fr": "Ouvrir le Terminal Paper",
        "es": "Abrir Terminal Paper",
        "pt": "Abrir Terminal Paper",
    },
    "dashboard.connect_live": {
        "en": "Launch Live Trading Terminal",
        "fr": "Lancer le Terminal Live",
        "es": "Abrir Terminal Live",
        "pt": "Abrir Terminal Live",
    },
    "dashboard.loading_connecting": {
        "en": "Connecting Session...",
        "fr": "Connexion de la Session...",
        "es": "Conectando Sesion...",
        "pt": "Conectando Sessao...",
    },
    "dashboard.warning_missing_credentials_title": {
        "en": "Missing Credentials",
        "fr": "Identifiants Manquants",
        "es": "Faltan Credenciales",
        "pt": "Credenciais Ausentes",
    },
    "dashboard.warning_missing_credentials_body": {
        "en": "API credentials are required for this broker.",
        "fr": "Les identifiants API sont requis pour ce broker.",
        "es": "Las credenciales API son obligatorias para este broker.",
        "pt": "As credenciais de API sao obrigatorias para este broker.",
    },
    "dashboard.warning_missing_secret_title": {
        "en": "Missing Secret Seed",
        "fr": "Seed Secrete Manquante",
        "es": "Falta la Seed Secreta",
        "pt": "Seed Secreta Ausente",
    },
    "dashboard.warning_missing_secret_body": {
        "en": "Stellar requires the account secret seed to sign offers.",
        "fr": "Stellar exige la seed secrete du compte pour signer les offres.",
        "es": "Stellar requiere la seed secreta de la cuenta para firmar ofertas.",
        "pt": "A Stellar exige a seed secreta da conta para assinar ofertas.",
    },
    "dashboard.warning_missing_account_title": {
        "en": "Missing Account ID",
        "fr": "ID Compte Manquant",
        "es": "Falta el ID de Cuenta",
        "pt": "ID da Conta Ausente",
    },
    "dashboard.warning_missing_account_body": {
        "en": "Account ID is required for Oanda sessions.",
        "fr": "L'ID de compte est requis pour les sessions Oanda.",
        "es": "El ID de cuenta es obligatorio para sesiones Oanda.",
        "pt": "O ID da conta e obrigatorio para sessoes Oanda.",
    },
    "terminal.window_title": {
        "en": "TradeAdviser Terminal",
        "fr": "Terminal TradeAdviser",
        "es": "Terminal TradeAdviser",
        "pt": "Terminal TradeAdviser",
    },
    "terminal.menu.file": {"en": "File", "fr": "Fichier", "es": "Archivo", "pt": "Arquivo"},
    "terminal.menu.trading": {"en": "Trading", "fr": "Trading", "es": "Trading", "pt": "Trading"},
    "terminal.menu.strategy": {"en": "Strategy", "fr": "Strategie", "es": "Estrategia", "pt": "Estrategia"},
    "terminal.menu.backtesting": {"en": "Backtesting", "fr": "Backtesting", "es": "Backtesting", "pt": "Backtesting"},
    "terminal.menu.charts": {"en": "Charts", "fr": "Graphiques", "es": "Graficos", "pt": "Graficos"},
    "terminal.menu.data": {"en": "Markets", "fr": "Marches", "es": "Mercados", "pt": "Mercados"},
    "terminal.menu.settings": {"en": "Preferences", "fr": "Preferences", "es": "Preferencias", "pt": "Preferencias"},
    "terminal.menu.risk": {"en": "Risk", "fr": "Risque", "es": "Riesgo", "pt": "Risco"},
    "terminal.menu.review": {"en": "Review", "fr": "Revue", "es": "Revision", "pt": "Revisao"},
    "terminal.menu.research": {"en": "Research", "fr": "Recherche", "es": "Investigacion", "pt": "Pesquisa"},
    "terminal.menu.language": {"en": "Language", "fr": "Langue", "es": "Idioma", "pt": "Idioma"},
    "terminal.menu.tools": {"en": "System", "fr": "Systeme", "es": "Sistema", "pt": "Sistema"},
    "terminal.menu.help": {"en": "Help", "fr": "Aide", "es": "Ayuda", "pt": "Ajuda"},
    "terminal.action.generate_report": {"en": "Generate Report", "fr": "Generer Rapport", "es": "Generar Reporte", "pt": "Gerar Relatorio"},
    "terminal.action.export_trades": {"en": "Export Trades", "fr": "Exporter Trades", "es": "Exportar Trades", "pt": "Exportar Trades"},
    "terminal.action.exit": {"en": "Exit", "fr": "Quitter", "es": "Salir", "pt": "Sair"},
    "terminal.action.start_auto": {"en": "Start Auto", "fr": "Lancer Auto", "es": "Iniciar Auto", "pt": "Iniciar Auto"},
    "terminal.action.stop_auto": {"en": "Stop Auto", "fr": "Arreter Auto", "es": "Detener Auto", "pt": "Parar Auto"},
    "terminal.action.manual_trade": {"en": "Manual Order", "fr": "Ordre Manuel", "es": "Orden Manual", "pt": "Ordem Manual"},
    "terminal.action.close_all": {"en": "Close Positions", "fr": "Clore Positions", "es": "Cerrar Posiciones", "pt": "Fechar Posicoes"},
    "terminal.action.cancel_all": {"en": "Cancel Orders", "fr": "Annuler Ordres", "es": "Cancelar Ordenes", "pt": "Cancelar Ordens"},
    "terminal.action.run_backtest": {"en": "Run Backtest", "fr": "Lancer Backtest", "es": "Ejecutar Backtest", "pt": "Executar Backtest"},
    "terminal.action.optimize": {"en": "Optimize", "fr": "Optimiser", "es": "Optimizar", "pt": "Otimizar"},
    "terminal.action.new_chart": {"en": "Open Chart", "fr": "Ouvrir Graphique", "es": "Abrir Grafico", "pt": "Abrir Grafico"},
    "terminal.action.multi_chart": {"en": "Multi-Chart", "fr": "Multi Graphique", "es": "Multi Grafico", "pt": "Multi Grafico"},
    "terminal.action.candle_colors": {"en": "Chart Colors", "fr": "Couleurs Graphique", "es": "Colores del Grafico", "pt": "Cores do Grafico"},
    "terminal.action.add_indicator": {"en": "Add Indicator", "fr": "Ajouter Indicateur", "es": "Agregar Indicador", "pt": "Adicionar Indicador"},
    "terminal.action.toggle_bid_ask": {"en": "Bid/Ask Lines", "fr": "Lignes Bid/Ask", "es": "Lineas Bid/Ask", "pt": "Linhas Bid/Ask"},
    "terminal.action.refresh_markets": {"en": "Reload Markets", "fr": "Recharger Marches", "es": "Recargar Mercados", "pt": "Recarregar Mercados"},
    "terminal.action.refresh_chart": {"en": "Reload Chart", "fr": "Recharger Graphique", "es": "Recargar Grafico", "pt": "Recarregar Grafico"},
    "terminal.action.refresh_orderbook": {"en": "Reload Orderbook", "fr": "Recharger Carnet", "es": "Recargar Orderbook", "pt": "Recarregar Orderbook"},
    "terminal.action.reload_balance": {"en": "Reload Balances", "fr": "Recharger Soldes", "es": "Recargar Saldos", "pt": "Recarregar Saldos"},
    "terminal.action.app_settings": {"en": "Preferences", "fr": "Preferences", "es": "Preferencias", "pt": "Preferencias"},
    "terminal.action.risk_settings": {"en": "Risk Settings", "fr": "Reglages Risque", "es": "Ajustes de Riesgo", "pt": "Ajustes de Risco"},
    "terminal.action.portfolio": {"en": "Exposure", "fr": "Exposition", "es": "Exposicion", "pt": "Exposicao"},
    "terminal.action.ml_monitor": {"en": "Signal Monitor", "fr": "Suivi Signaux", "es": "Monitor de Senales", "pt": "Monitor de Sinais"},
    "terminal.action.logs": {"en": "Logs", "fr": "Journaux", "es": "Registros", "pt": "Logs"},
    "terminal.action.performance": {"en": "Performance", "fr": "Performance", "es": "Rendimiento", "pt": "Performance"},
    "terminal.action.documentation": {"en": "User Guide", "fr": "Guide Utilisateur", "es": "Guia de Usuario", "pt": "Guia do Usuario"},
    "terminal.action.api_reference": {"en": "API Guide", "fr": "Guide API", "es": "Guia API", "pt": "Guia API"},
    "terminal.action.about": {"en": "About Sopotek", "fr": "A propos de Sopotek", "es": "Acerca de Sopotek", "pt": "Sobre o Sopotek"},
    "terminal.toolbar.symbol": {"en": "Symbol", "fr": "Symbole", "es": "Simbolo", "pt": "Simbolo"},
    "terminal.toolbar.open_symbol": {"en": "Open Symbol", "fr": "Ouvrir Symbole", "es": "Abrir Simbolo", "pt": "Abrir Simbolo"},
    "terminal.toolbar.timeframe": {"en": "Timeframe", "fr": "Unite", "es": "Marco Temporal", "pt": "Periodo"},
    "terminal.toolbar.timeframe_active": {
        "en": "Timeframe  {timeframe}",
        "fr": "Unite  {timeframe}",
        "es": "Marco Temporal  {timeframe}",
        "pt": "Periodo  {timeframe}",
    },
    "terminal.toolbar.screenshot": {"en": "Screenshot", "fr": "Capture", "es": "Captura", "pt": "Captura"},
    "terminal.autotrade.on": {"en": "AI Trading  ON", "fr": "Trading IA  ON", "es": "Trading IA  ON", "pt": "Trading IA  ON"},
    "terminal.autotrade.off": {"en": "AI Trading  OFF", "fr": "Trading IA  OFF", "es": "Trading IA  OFF", "pt": "Trading IA  OFF"},
    "terminal.status.connected": {"en": "CONNECTED", "fr": "CONNECTE", "es": "CONECTADO", "pt": "CONECTADO"},
    "terminal.status.disconnected": {"en": "DISCONNECTED", "fr": "DECONNECTE", "es": "DESCONECTADO", "pt": "DESCONECTADO"},
    "terminal.status.connecting": {"en": "CONNECTING", "fr": "CONNEXION", "es": "CONECTANDO", "pt": "CONECTANDO"},
    "terminal.warning.trading_not_ready_title": {
        "en": "Trading Not Ready",
        "fr": "Trading Non Pret",
        "es": "Trading No Listo",
        "pt": "Trading Nao Pronto",
    },
    "terminal.warning.trading_not_ready_body": {
        "en": "Connect broker first before starting auto trading.",
        "fr": "Connectez d'abord le broker avant de lancer l'auto trading.",
        "es": "Conecta primero el broker antes de iniciar auto trading.",
        "pt": "Conecte primeiro o broker antes de iniciar auto trading.",
    },
    "terminal.dialog.new_chart_title": {"en": "New Chart", "fr": "Nouveau Graphique", "es": "Nuevo Grafico", "pt": "Novo Grafico"},
    "terminal.dialog.new_chart_prompt": {"en": "Enter Symbol:", "fr": "Entrer le Symbole:", "es": "Ingresa el Simbolo:", "pt": "Digite o Simbolo:"},
}


LITERAL_TRANSLATIONS = {
    "CONNECT": {"en": "CONNECT", "fr": "CONNECTER", "es": "CONECTAR", "pt": "CONECTAR"},
    "Strategy": {"en": "Strategy", "fr": "Strategie", "es": "Estrategia", "pt": "Estrategia"},
    "Emergency Kill Switch": {
        "en": "Emergency Kill Switch",
        "fr": "Arret d urgence",
        "es": "Interruptor de emergencia",
        "pt": "Parada de emergencia",
    },
    "Strategy Optimization": {
        "en": "Strategy Optimization",
        "fr": "Optimisation de strategie",
        "es": "Optimizacion de estrategia",
        "pt": "Otimizacao de estrategia",
    },
    "Detach Current Tab": {
        "en": "Detach Current Tab",
        "fr": "Detacher l onglet actif",
        "es": "Separar pestana actual",
        "pt": "Desanexar aba atual",
    },
    "Reattach Active Chart": {
        "en": "Reattach Active Chart",
        "fr": "Rattacher le graphique actif",
        "es": "Reanclar grafico activo",
        "pt": "Reanexar grafico ativo",
    },
    "Tile Chart Windows": {
        "en": "Tile Chart Windows",
        "fr": "Mosaïque des fenetres de graphique",
        "es": "Organizar ventanas de graficos",
        "pt": "Organizar janelas de graficos",
    },
    "Cascade Chart Windows": {
        "en": "Cascade Chart Windows",
        "fr": "Cascader les fenetres de graphique",
        "es": "Cascada de ventanas de graficos",
        "pt": "Cascata de janelas de graficos",
    },
    "Volume Bar": {"en": "Volume Bar", "fr": "Barre de volume", "es": "Barra de volumen", "pt": "Barra de volume"},
    "Sopotek Pilot": {"en": "Sopotek Pilot", "fr": "Sopotek Pilot", "es": "Sopotek Pilot", "pt": "Sopotek Pilot"},
    "Recommendations": {"en": "Recommendations", "fr": "Recommandations", "es": "Recomendaciones", "pt": "Recomendacoes"},
    "Closed Journal": {"en": "Closed Journal", "fr": "Journal ferme", "es": "Diario cerrado", "pt": "Diario fechado"},
    "Trade Checklist": {"en": "Trade Checklist", "fr": "Checklist de trade", "es": "Checklist de trading", "pt": "Checklist de trade"},
    "Journal Review": {"en": "Journal Review", "fr": "Revue du journal", "es": "Revision del diario", "pt": "Revisao do diario"},
    "System Health": {"en": "System Health", "fr": "Sante systeme", "es": "Salud del sistema", "pt": "Saude do sistema"},
    "Quant PM": {"en": "Quant PM", "fr": "Quant PM", "es": "Quant PM", "pt": "Quant PM"},
    "ML Research Lab": {"en": "ML Research Lab", "fr": "Lab recherche ML", "es": "Laboratorio ML", "pt": "Laboratorio ML"},
    "Position Analysis": {"en": "Position Analysis", "fr": "Analyse des positions", "es": "Analisis de posiciones", "pt": "Analise de posicoes"},
    "Strategy Assigner": {"en": "Strategy Assigner", "fr": "Affectation strategie", "es": "Asignador de estrategia", "pt": "Atribuidor de estrategia"},
    "Strategy Scorecard": {"en": "Strategy Scorecard", "fr": "Score strategie", "es": "Tarjeta de estrategia", "pt": "Painel de estrategia"},
    "Strategy Debug": {"en": "Strategy Debug", "fr": "Debug strategie", "es": "Depuracion de estrategia", "pt": "Debug de estrategia"},
    "System Console": {"en": "System Console", "fr": "Console systeme", "es": "Consola del sistema", "pt": "Console do sistema"},
    "System Status": {"en": "System Status", "fr": "Statut systeme", "es": "Estado del sistema", "pt": "Status do sistema"},
    "Stellar Asset Explorer": {
        "en": "Stellar Asset Explorer",
        "fr": "Explorateur d actifs Stellar",
        "es": "Explorador de activos Stellar",
        "pt": "Explorador de ativos Stellar",
    },
    "License": {"en": "License", "fr": "Licence", "es": "Licencia", "pt": "Licenca"},
    "Status": {"en": "Status", "fr": "Statut", "es": "Estado", "pt": "Status"},
    "Show or hide the System Status panel": {
        "en": "Show or hide the System Status panel",
        "fr": "Afficher ou masquer le panneau de statut systeme",
        "es": "Mostrar u ocultar el panel de estado del sistema",
        "pt": "Mostrar ou ocultar o painel de status do sistema",
    },
    "Shows whether AI trading is currently active": {
        "en": "Shows whether AI trading is currently active",
        "fr": "Indique si le trading IA est actif",
        "es": "Muestra si el trading IA esta activo",
        "pt": "Mostra se o trading IA esta ativo",
    },
    "Timeframe": {"en": "Timeframe", "fr": "Unite", "es": "Marco temporal", "pt": "Periodo"},
    "Info": {"en": "Info", "fr": "Infos", "es": "Info", "pt": "Info"},
    "Candlestick": {"en": "Candlestick", "fr": "Bougies", "es": "Velas", "pt": "Candles"},
    "Depth Chart": {"en": "Depth Chart", "fr": "Graphique de profondeur", "es": "Grafico de profundidad", "pt": "Grafico de profundidade"},
    "Market Info": {"en": "Market Info", "fr": "Infos marche", "es": "Info de mercado", "pt": "Info de mercado"},
    "Select the timeframe for this chart.": {
        "en": "Select the timeframe for this chart.",
        "fr": "Selectionnez l unite de temps pour ce graphique.",
        "es": "Selecciona el marco temporal para este grafico.",
        "pt": "Selecione o periodo para este grafico.",
    },
    "Depth chart will populate when live order book data arrives.": {
        "en": "Depth chart will populate when live order book data arrives.",
        "fr": "Le graphique de profondeur se remplira avec le carnet en direct.",
        "es": "El grafico de profundidad se llenara con el libro de ordenes en vivo.",
        "pt": "O grafico de profundidade sera preenchido com o livro de ofertas ao vivo.",
    },
    "Market details will update with ticker, candle, and order book context.": {
        "en": "Market details will update with ticker, candle, and order book context.",
        "fr": "Les details de marche seront mis a jour avec ticker, bougies et carnet.",
        "es": "Los detalles del mercado se actualizaran con ticker, velas y libro de ordenes.",
        "pt": "Os detalhes do mercado serao atualizados com ticker, candles e livro de ofertas.",
    },
    "Price": {"en": "Price", "fr": "Prix", "es": "Precio", "pt": "Preco"},
    "Volume": {"en": "Volume", "fr": "Volume", "es": "Volumen", "pt": "Volume"},
    "Orderbook": {"en": "Orderbook", "fr": "Carnet d ordres", "es": "Libro de ordenes", "pt": "Livro de ofertas"},
    "Date / Time (UTC)": {"en": "Date / Time (UTC)", "fr": "Date / Heure (UTC)", "es": "Fecha / Hora (UTC)", "pt": "Data / Hora (UTC)"},
    "Last": {"en": "Last", "fr": "Dernier", "es": "Ultimo", "pt": "Ultimo"},
    "Mid": {"en": "Mid", "fr": "Milieu", "es": "Medio", "pt": "Medio"},
    "Spread": {"en": "Spread", "fr": "Spread", "es": "Spread", "pt": "Spread"},
    "Best Bid": {"en": "Best Bid", "fr": "Meilleur bid", "es": "Mejor bid", "pt": "Melhor bid"},
    "Best Ask": {"en": "Best Ask", "fr": "Mejor ask", "es": "Mejor ask", "pt": "Melhor ask"},
    "Range": {"en": "Range", "fr": "Plage", "es": "Rango", "pt": "Faixa"},
    "Visible Vol": {"en": "Visible Vol", "fr": "Vol visible", "es": "Vol visible", "pt": "Vol visivel"},
    "Depth Bias": {"en": "Depth Bias", "fr": "Biais profondeur", "es": "Sesgo de profundidad", "pt": "Vies de profundidade"},
    "Market Watch": {"en": "Market Watch", "fr": "Surveillance marche", "es": "Vigilancia de mercado", "pt": "Monitor de mercado"},
    "Tick Chart": {"en": "Tick Chart", "fr": "Graphique tick", "es": "Grafico tick", "pt": "Grafico tick"},
    "Equity Curve": {"en": "Equity Curve", "fr": "Courbe d equity", "es": "Curva de equity", "pt": "Curva de equity"},
    "Performance": {"en": "Performance", "fr": "Performance", "es": "Rendimiento", "pt": "Performance"},
    "Market Regime": {"en": "Market Regime", "fr": "Regime de marche", "es": "Regimen de mercado", "pt": "Regime de mercado"},
    "Portfolio Exposure": {"en": "Portfolio Exposure", "fr": "Exposition portefeuille", "es": "Exposicion de cartera", "pt": "Exposicao da carteira"},
    "Model Confidence": {"en": "Model Confidence", "fr": "Confiance modele", "es": "Confianza del modelo", "pt": "Confianca do modelo"},
    "Watch": {"en": "Watch", "fr": "Suivi", "es": "Seguir", "pt": "Observar"},
    "Symbol": {"en": "Symbol", "fr": "Symbole", "es": "Simbolo", "pt": "Simbolo"},
    "Bid": {"en": "Bid", "fr": "Bid", "es": "Bid", "pt": "Bid"},
    "Ask": {"en": "Ask", "fr": "Ask", "es": "Ask", "pt": "Ask"},
    "USD Value": {"en": "USD Value", "fr": "Valeur USD", "es": "Valor USD", "pt": "Valor USD"},
    "AI Training": {"en": "AI Training", "fr": "Entrainement IA", "es": "Entrenamiento IA", "pt": "Treinamento IA"},
    "Action": {"en": "Action", "fr": "Action", "es": "Accion", "pt": "Acao"},
    "Side": {"en": "Side", "fr": "Sens", "es": "Lado", "pt": "Lado"},
    "Units": {"en": "Units", "fr": "Unites", "es": "Unidades", "pt": "Unidades"},
    "Amount": {"en": "Amount", "fr": "Montant", "es": "Cantidad", "pt": "Quantidade"},
    "Entry": {"en": "Entry", "fr": "Entree", "es": "Entrada", "pt": "Entrada"},
    "Mark": {"en": "Mark", "fr": "Marque", "es": "Marca", "pt": "Marcacao"},
    "Value": {"en": "Value", "fr": "Valeur", "es": "Valor", "pt": "Valor"},
    "Unrealized P/L": {"en": "Unrealized P/L", "fr": "P/L latent", "es": "P/L no realizado", "pt": "P/L nao realizado"},
    "Realized P/L": {"en": "Realized P/L", "fr": "P/L realise", "es": "P/L realizado", "pt": "P/L realizado"},
    "Financing": {"en": "Financing", "fr": "Financement", "es": "Financiacion", "pt": "Financiamento"},
    "Margin Used": {"en": "Margin Used", "fr": "Marge utilisee", "es": "Margen usado", "pt": "Margem usada"},
    "Resettable P/L": {"en": "Resettable P/L", "fr": "P/L reinitialisable", "es": "P/L reiniciable", "pt": "P/L reiniciavel"},
    "Mode": {"en": "Mode", "fr": "Mode", "es": "Modo", "pt": "Modo"},
    "Trades": {"en": "Trades", "fr": "Trades", "es": "Operaciones", "pt": "Trades"},
    "Win Rate": {"en": "Win Rate", "fr": "Taux de gain", "es": "Tasa de acierto", "pt": "Taxa de acerto"},
    "Avg PnL": {"en": "Avg PnL", "fr": "PnL moyen", "es": "PnL medio", "pt": "PnL medio"},
    "Fees": {"en": "Fees", "fr": "Frais", "es": "Comisiones", "pt": "Taxas"},
    "Check": {"en": "Check", "fr": "Controle", "es": "Chequeo", "pt": "Cheque"},
    "Detail": {"en": "Detail", "fr": "Detail", "es": "Detalle", "pt": "Detalhe"},
    "Source": {"en": "Source", "fr": "Source", "es": "Fuente", "pt": "Fonte"},
    "Confidence": {"en": "Confidence", "fr": "Confiance", "es": "Confianza", "pt": "Confianca"},
    "Why": {"en": "Why", "fr": "Pourquoi", "es": "Por que", "pt": "Por que"},
    "Time": {"en": "Time", "fr": "Heure", "es": "Hora", "pt": "Hora"},
    "Direction": {"en": "Direction", "fr": "Direction", "es": "Direccion", "pt": "Direcao"},
    "Exposure": {"en": "Exposure", "fr": "Exposition", "es": "Exposicion", "pt": "Exposicao"},
    "% Equity": {"en": "% Equity", "fr": "% Equity", "es": "% Equity", "pt": "% Equity"},
    "Ranked": {"en": "Ranked", "fr": "Classe", "es": "Clasificado", "pt": "Rankeado"},
    "Live": {"en": "Live", "fr": "Live", "es": "Live", "pt": "Live"},
    "Agent": {"en": "Agent", "fr": "Agent", "es": "Agente", "pt": "Agente"},
    "Stage": {"en": "Stage", "fr": "Etape", "es": "Etapa", "pt": "Etapa"},
    "Samples": {"en": "Samples", "fr": "Echantillons", "es": "Muestras", "pt": "Amostras"},
    "Avg P/L": {"en": "Avg P/L", "fr": "P/L moyen", "es": "P/L medio", "pt": "P/L medio"},
    "Scope": {"en": "Scope", "fr": "Portee", "es": "Alcance", "pt": "Escopo"},
    "Experiment": {"en": "Experiment", "fr": "Experience", "es": "Experimento", "pt": "Experimento"},
    "Window": {"en": "Window", "fr": "Fenetre", "es": "Ventana", "pt": "Janela"},
    "Train Rows": {"en": "Train Rows", "fr": "Lignes train", "es": "Filas train", "pt": "Linhas train"},
    "Test Rows": {"en": "Test Rows", "fr": "Lignes test", "es": "Filas test", "pt": "Linhas test"},
    "Accuracy": {"en": "Accuracy", "fr": "Precision", "es": "Exactitud", "pt": "Acuracia"},
    "Precision": {"en": "Precision", "fr": "Precision", "es": "Precision", "pt": "Precisao"},
    "Recall": {"en": "Recall", "fr": "Rappel", "es": "Recall", "pt": "Recall"},
    "Avg Conf.": {"en": "Avg Conf.", "fr": "Conf moy.", "es": "Conf prom.", "pt": "Conf media"},
    "Strategy Tester": {"en": "Strategy Tester", "fr": "Testeur de strategie", "es": "Probador de estrategia", "pt": "Testador de estrategia"},
    "Strategy tester ready.": {
        "en": "Strategy tester ready.",
        "fr": "Le testeur de strategie est pret.",
        "es": "El probador de estrategia esta listo.",
        "pt": "O testador de estrategia esta pronto.",
    },
    "Backtest Symbol": {"en": "Backtest Symbol", "fr": "Symbole backtest", "es": "Simbolo backtest", "pt": "Simbolo do backtest"},
    "Backtest Strategy": {"en": "Backtest Strategy", "fr": "Strategie backtest", "es": "Estrategia backtest", "pt": "Estrategia do backtest"},
    "Start Date": {"en": "Start Date", "fr": "Date de debut", "es": "Fecha de inicio", "pt": "Data inicial"},
    "End Date": {"en": "End Date", "fr": "Date de fin", "es": "Fecha final", "pt": "Data final"},
    "Target Bars": {"en": "Target Bars", "fr": "Barres cibles", "es": "Barras objetivo", "pt": "Barras alvo"},
    "Expert": {"en": "Expert", "fr": "Expert", "es": "Experto", "pt": "Especialista"},
    "Period": {"en": "Period", "fr": "Periode", "es": "Periodo", "pt": "Periodo"},
    "Initial Deposit": {"en": "Initial Deposit", "fr": "Depot initial", "es": "Deposito inicial", "pt": "Deposito inicial"},
    "Start Backtest": {"en": "Start Backtest", "fr": "Demarrer backtest", "es": "Iniciar backtest", "pt": "Iniciar backtest"},
    "Load Exchange Data": {"en": "Load Exchange Data", "fr": "Charger les donnees marche", "es": "Cargar datos del mercado", "pt": "Carregar dados do mercado"},
    "Generate Report": {"en": "Generate Report", "fr": "Generer rapport", "es": "Generar reporte", "pt": "Gerar relatorio"},
    "Results": {"en": "Results", "fr": "Resultats", "es": "Resultados", "pt": "Resultados"},
    "Graph": {"en": "Graph", "fr": "Graphique", "es": "Grafico", "pt": "Grafico"},
    "Report": {"en": "Report", "fr": "Rapport", "es": "Reporte", "pt": "Relatorio"},
    "Journal": {"en": "Journal", "fr": "Journal", "es": "Diario", "pt": "Diario"},
    "Backtest stop requested...": {
        "en": "Backtest stop requested...",
        "fr": "Arret du backtest demande...",
        "es": "Se solicito detener el backtest...",
        "pt": "Parada do backtest solicitada...",
    },
    "Backtest running...": {"en": "Backtest running...", "fr": "Backtest en cours...", "es": "Backtest en ejecucion...", "pt": "Backtest em execucao..."},
    "Backtest engine not initialized.": {
        "en": "Backtest engine not initialized.",
        "fr": "Le moteur de backtest n est pas initialise.",
        "es": "El motor de backtest no esta inicializado.",
        "pt": "O motor de backtest nao esta inicializado.",
    },
    "Loading Exchange Data...": {
        "en": "Loading Exchange Data...",
        "fr": "Chargement des donnees marche...",
        "es": "Cargando datos del mercado...",
        "pt": "Carregando dados do mercado...",
    },
    "Bar-close simulation": {
        "en": "Bar-close simulation",
        "fr": "Simulation en cloture de bougie",
        "es": "Simulacion al cierre de vela",
        "pt": "Simulacao no fechamento da vela",
    },
    "No backtest results yet.": {
        "en": "No backtest results yet.",
        "fr": "Aucun resultat de backtest pour le moment.",
        "es": "Todavia no hay resultados de backtest.",
        "pt": "Ainda nao ha resultados de backtest.",
    },
    "Choose your symbol and click Run Optimization or Rank All Strategies to start.": {
        "en": "Choose your symbol and click Run Optimization or Rank All Strategies to start.",
        "fr": "Choisissez votre symbole puis cliquez sur Lancer optimisation ou Classer toutes les strategies.",
        "es": "Elige tu simbolo y haz clic en Ejecutar optimizacion o Clasificar todas las estrategias.",
        "pt": "Escolha seu simbolo e clique em Executar otimizacao ou Classificar todas as estrategias.",
    },
    "Optimize Symbol": {"en": "Optimize Symbol", "fr": "Optimiser symbole", "es": "Optimizar simbolo", "pt": "Otimizar simbolo"},
    "Optimize Strategy": {"en": "Optimize Strategy", "fr": "Optimiser strategie", "es": "Optimizar estrategia", "pt": "Otimizar estrategia"},
    "Run Optimization": {"en": "Run Optimization", "fr": "Lancer optimisation", "es": "Ejecutar optimizacion", "pt": "Executar otimizacao"},
    "Rank All Strategies": {"en": "Rank All Strategies", "fr": "Classer toutes les strategies", "es": "Clasificar todas las estrategias", "pt": "Classificar todas as estrategias"},
    "Apply Best Params": {"en": "Apply Best Params", "fr": "Appliquer meilleurs parametres", "es": "Aplicar mejores parametros", "pt": "Aplicar melhores parametros"},
    "Assign Best To Symbol": {"en": "Assign Best To Symbol", "fr": "Affecter le meilleur au symbole", "es": "Asignar la mejor al simbolo", "pt": "Atribuir a melhor ao simbolo"},
    "Assign Top": {"en": "Assign Top", "fr": "Affecter top", "es": "Asignar top", "pt": "Atribuir topo"},
    "Optimization workspace ready.": {
        "en": "Optimization workspace ready.",
        "fr": "L espace d optimisation est pret.",
        "es": "El espacio de optimizacion esta listo.",
        "pt": "O espaco de otimizacao esta pronto.",
    },
    "Running...": {"en": "Running...", "fr": "Execution...", "es": "Ejecutando...", "pt": "Executando..."},
    "Score": {"en": "Score", "fr": "Score", "es": "Puntuacion", "pt": "Pontuacao"},
    "Profit": {"en": "Profit", "fr": "Profit", "es": "Beneficio", "pt": "Lucro"},
    "Drawdown": {"en": "Drawdown", "fr": "Drawdown", "es": "Drawdown", "pt": "Drawdown"},
    "Closed Trades": {"en": "Closed Trades", "fr": "Trades clotures", "es": "Operaciones cerradas", "pt": "Trades fechados"},
    "Rank All": {"en": "Rank All", "fr": "Classer tout", "es": "Clasificar todo", "pt": "Classificar tudo"},
    "Parameter Optimize": {"en": "Parameter Optimize", "fr": "Optimisation des parametres", "es": "Optimizacion de parametros", "pt": "Otimizacao de parametros"},
    "Notification Center": {"en": "Notification Center", "fr": "Centre de notifications", "es": "Centro de notificaciones", "pt": "Central de notificacoes"},
    "Notifications collect fills, rejects, disconnects, stale market-data warnings, and guard events.": {
        "en": "Notifications collect fills, rejects, disconnects, stale market-data warnings, and guard events.",
        "fr": "Les notifications regroupent executions, rejets, deconnexions, alertes de donnees stale et evenements de garde.",
        "es": "Las notificaciones agrupan ejecuciones, rechazos, desconexiones, alertas de datos obsoletos y eventos de proteccion.",
        "pt": "As notificacoes agrupam execucoes, rejeicoes, desconexoes, alertas de dados defasados e eventos de protecao.",
    },
    "Filter notifications": {"en": "Filter notifications", "fr": "Filtrer notifications", "es": "Filtrar notificaciones", "pt": "Filtrar notificacoes"},
    "Clear": {"en": "Clear", "fr": "Effacer", "es": "Limpiar", "pt": "Limpar"},
    "Event": {"en": "Event", "fr": "Evenement", "es": "Evento", "pt": "Evento"},
    "Details": {"en": "Details", "fr": "Details", "es": "Detalles", "pt": "Detalhes"},
    "Live Agent Timeline": {"en": "Live Agent Timeline", "fr": "Chronologie agent live", "es": "Linea de tiempo de agentes", "pt": "Linha do tempo de agentes"},
    "Watch the live multi-agent flow across symbols, from signal selection through risk and execution.": {
        "en": "Watch the live multi-agent flow across symbols, from signal selection through risk and execution.",
        "fr": "Suivez le flux multi agent en direct entre symboles, du signal au risque puis a l execution.",
        "es": "Sigue el flujo multiagente en vivo entre simbolos, desde la senal hasta riesgo y ejecucion.",
        "pt": "Acompanhe o fluxo multiagente ao vivo entre simbolos, do sinal ao risco e execucao.",
    },
    "Filter by symbol, agent, event, strategy, timeframe, or message": {
        "en": "Filter by symbol, agent, event, strategy, timeframe, or message",
        "fr": "Filtrer par symbole, agent, evenement, strategie, unite ou message",
        "es": "Filtrar por simbolo, agente, evento, estrategia, marco temporal o mensaje",
        "pt": "Filtrar por simbolo, agente, evento, estrategia, periodo ou mensagem",
    },
    "All Statuses": {"en": "All Statuses", "fr": "Tous les statuts", "es": "Todos los estados", "pt": "Todos os status"},
    "All Timeframes": {"en": "All Timeframes", "fr": "Toutes les unites", "es": "Todos los marcos temporales", "pt": "Todos os periodos"},
    "All Strategies": {"en": "All Strategies", "fr": "Toutes les strategies", "es": "Todas las estrategias", "pt": "Todas as estrategias"},
    "Refresh": {"en": "Refresh", "fr": "Actualiser", "es": "Actualizar", "pt": "Atualizar"},
    "Clear Filters": {"en": "Clear Filters", "fr": "Effacer filtres", "es": "Limpiar filtros", "pt": "Limpar filtros"},
    "Pin Selected Symbol": {"en": "Pin Selected Symbol", "fr": "Epingler symbole selectionne", "es": "Fijar simbolo seleccionado", "pt": "Fixar simbolo selecionado"},
    "Expand All": {"en": "Expand All", "fr": "Tout ouvrir", "es": "Expandir todo", "pt": "Expandir tudo"},
    "Collapse All": {"en": "Collapse All", "fr": "Tout reduire", "es": "Colapsar todo", "pt": "Recolher tudo"},
    "Replay Latest Chain": {"en": "Replay Latest Chain", "fr": "Rejouer la derniere chaine", "es": "Repetir la ultima cadena", "pt": "Repetir a ultima cadeia"},
    "Approved": {"en": "Approved", "fr": "Approuve", "es": "Aprobado", "pt": "Aprovado"},
    "Rejected": {"en": "Rejected", "fr": "Rejete", "es": "Rechazado", "pt": "Rejeitado"},
    "Visible Symbols": {"en": "Visible Symbols", "fr": "Symboles visibles", "es": "Simbolos visibles", "pt": "Simbolos visiveis"},
    "No active symbols": {"en": "No active symbols", "fr": "Aucun symbole actif", "es": "No hay simbolos activos", "pt": "Nenhum simbolo ativo"},
    "Last Minute": {"en": "Last Minute", "fr": "Derniere minute", "es": "Ultimo minuto", "pt": "Ultimo minuto"},
    "Changes": {"en": "Changes", "fr": "Changements", "es": "Cambios", "pt": "Mudancas"},
    "Open Strategy Assigner": {"en": "Open Strategy Assigner", "fr": "Ouvrir assignation strategie", "es": "Abrir asignador de estrategia", "pt": "Abrir atribuidor de estrategia"},
    "Refresh Symbol": {"en": "Refresh Symbol", "fr": "Actualiser symbole", "es": "Actualizar simbolo", "pt": "Atualizar simbolo"},
    "Acknowledge Anomaly": {"en": "Acknowledge Anomaly", "fr": "Acquitter anomalie", "es": "Reconocer anomalia", "pt": "Reconhecer anomalia"},
    "Agent / Event": {"en": "Agent / Event", "fr": "Agent / evenement", "es": "Agente / evento", "pt": "Agente / evento"},
    "Current Assignment": {"en": "Current Assignment", "fr": "Affectation actuelle", "es": "Asignacion actual", "pt": "Atribuicao atual"},
    "Latest Agent Recommendation": {
        "en": "Latest Agent Recommendation",
        "fr": "Derniere recommandation agent",
        "es": "Ultima recomendacion del agente",
        "pt": "Ultima recomendacao do agente",
    },
    "Select a symbol to inspect its active routing.": {
        "en": "Select a symbol to inspect its active routing.",
        "fr": "Selectionnez un symbole pour inspecter son routage actif.",
        "es": "Selecciona un simbolo para inspeccionar su enrutamiento activo.",
        "pt": "Selecione um simbolo para inspecionar seu roteamento ativo.",
    },
    "Select a symbol to inspect the latest decision.": {
        "en": "Select a symbol to inspect the latest decision.",
        "fr": "Selectionnez un symbole pour inspecter la derniere decision.",
        "es": "Selecciona un simbolo para inspeccionar la ultima decision.",
        "pt": "Selecione um simbolo para inspecionar a ultima decisao.",
    },
    "Select a symbol or event to inspect the live agent payload.": {
        "en": "Select a symbol or event to inspect the live agent payload.",
        "fr": "Selectionnez un symbole ou un evenement pour inspecter la charge agent live.",
        "es": "Selecciona un simbolo o evento para inspeccionar la carga del agente en vivo.",
        "pt": "Selecione um simbolo ou evento para inspecionar a carga do agente ao vivo.",
    },
    "No recent agent decision has been recorded yet.": {
        "en": "No recent agent decision has been recorded yet.",
        "fr": "Aucune decision agent recente n a encore ete enregistree.",
        "es": "Todavia no se ha registrado una decision reciente del agente.",
        "pt": "Ainda nao foi registrada uma decisao recente do agente.",
    },
    "Locked": {"en": "Locked", "fr": "Verrouille", "es": "Bloqueado", "pt": "Bloqueado"},
    "Pending": {"en": "Pending", "fr": "En attente", "es": "Pendiente", "pt": "Pendente"},
    "Reason": {"en": "Reason", "fr": "Raison", "es": "Motivo", "pt": "Motivo"},
    "Execution": {"en": "Execution", "fr": "Execution", "es": "Ejecucion", "pt": "Execucao"},
    "Default": {"en": "Default", "fr": "Defaut", "es": "Predeterminado", "pt": "Padrao"},
    "Single": {"en": "Single", "fr": "Unique", "es": "Unico", "pt": "Unico"},
    "Ranked Mix": {"en": "Ranked Mix", "fr": "Mix classe", "es": "Mezcla clasificada", "pt": "Mix ranqueado"},
    "Yes": {"en": "Yes", "fr": "Oui", "es": "Si", "pt": "Sim"},
    "No": {"en": "No", "fr": "Non", "es": "No", "pt": "Nao"},
    "Set symbol, side, size, entry, stop loss, and take profit before sending the order.": {
        "en": "Set symbol, side, size, entry, stop loss, and take profit before sending the order.",
        "fr": "Definissez symbole, sens, taille, entree, stop loss et take profit avant d envoyer l ordre.",
        "es": "Define simbolo, lado, tamano, entrada, stop loss y take profit antes de enviar la orden.",
        "pt": "Defina simbolo, lado, tamanho, entrada, stop loss e take profit antes de enviar a ordem.",
    },
    "Order Type": {"en": "Order Type", "fr": "Type d ordre", "es": "Tipo de orden", "pt": "Tipo de ordem"},
    "Size In": {"en": "Size In", "fr": "Taille en", "es": "Tamano en", "pt": "Tamanho em"},
    "Entry Price": {"en": "Entry Price", "fr": "Prix d entree", "es": "Precio de entrada", "pt": "Preco de entrada"},
    "Stop Trigger": {"en": "Stop Trigger", "fr": "Declencheur stop", "es": "Disparador stop", "pt": "Gatilho stop"},
    "Stop Loss": {"en": "Stop Loss", "fr": "Stop loss", "es": "Stop loss", "pt": "Stop loss"},
    "Take Profit": {"en": "Take Profit", "fr": "Take profit", "es": "Take profit", "pt": "Take profit"},
    "Buy Market": {"en": "Buy Market", "fr": "Acheter marche", "es": "Comprar mercado", "pt": "Comprar mercado"},
    "Sell Market": {"en": "Sell Market", "fr": "Vendre marche", "es": "Vender mercado", "pt": "Vender mercado"},
    "Submit Order": {"en": "Submit Order", "fr": "Envoyer ordre", "es": "Enviar orden", "pt": "Enviar ordem"},
    "Reset Ticket": {"en": "Reset Ticket", "fr": "Reinitialiser ticket", "es": "Restablecer ticket", "pt": "Redefinir ticket"},
    "Lots": {"en": "Lots", "fr": "Lots", "es": "Lotes", "pt": "Lotes"},
    "Order Book": {"en": "Order Book", "fr": "Carnet d ordres", "es": "Libro de ordenes", "pt": "Livro de ofertas"},
    "Recent Trades": {"en": "Recent Trades", "fr": "Trades recents", "es": "Operaciones recientes", "pt": "Trades recentes"},
    "Bid Depth": {"en": "Bid Depth", "fr": "Profondeur bid", "es": "Profundidad bid", "pt": "Profundidade bid"},
    "Bid Size": {"en": "Bid Size", "fr": "Taille bid", "es": "Tamano bid", "pt": "Tamanho bid"},
    "Bid Price": {"en": "Bid Price", "fr": "Prix bid", "es": "Precio bid", "pt": "Preco bid"},
    "Ask Price": {"en": "Ask Price", "fr": "Prix ask", "es": "Precio ask", "pt": "Preco ask"},
    "Ask Size": {"en": "Ask Size", "fr": "Taille ask", "es": "Tamano ask", "pt": "Tamanho ask"},
    "Ask Depth": {"en": "Ask Depth", "fr": "Profondeur ask", "es": "Profundidad ask", "pt": "Profundidade ask"},
    "Waiting for market trades.": {
        "en": "Waiting for market trades.",
        "fr": "En attente des trades de marche.",
        "es": "Esperando operaciones del mercado.",
        "pt": "Aguardando trades do mercado.",
    },
    "Recent public trades are unavailable for this symbol right now.": {
        "en": "Recent public trades are unavailable for this symbol right now.",
        "fr": "Les trades publics recents sont indisponibles pour ce symbole actuellement.",
        "es": "Las operaciones publicas recientes no estan disponibles para este simbolo ahora mismo.",
        "pt": "Os trades publicos recentes nao estao disponiveis para este simbolo agora.",
    },
    "Risk Heatmap": {"en": "Risk Heatmap", "fr": "Carte de chaleur du risque", "es": "Mapa de calor de riesgo", "pt": "Mapa de calor de risco"},
    "Risk heatmap is waiting for portfolio data.": {
        "en": "Risk heatmap is waiting for portfolio data.",
        "fr": "La carte de chaleur du risque attend les donnees portefeuille.",
        "es": "El mapa de calor de riesgo esta esperando datos de cartera.",
        "pt": "O mapa de calor de risco esta aguardando dados da carteira.",
    },
}


def _build_source_text_translations():
    source_texts = {}
    localized_to_source = {}

    for options in list(TRANSLATIONS.values()) + list(LITERAL_TRANSLATIONS.values()):
        english = str(options.get("en") or "").strip()
        if not english:
            continue
        source_texts.setdefault(english, options)
        for localized in options.values():
            text = str(localized or "").strip()
            if text:
                localized_to_source[text] = english

    return source_texts, localized_to_source


SOURCE_TEXT_TRANSLATIONS, LOCALIZED_TEXT_TO_SOURCE = _build_source_text_translations()


def normalize_language_code(code):
    text = str(code or DEFAULT_LANGUAGE).strip().lower()
    if text in SUPPORTED_LANGUAGES:
        return text
    if "-" in text:
        base = text.split("-", 1)[0]
        if base in SUPPORTED_LANGUAGES:
            return base
    return DEFAULT_LANGUAGE


def iter_supported_languages():
    for code, label in SUPPORTED_LANGUAGES.items():
        yield code, label


def translate(language_code, key, **kwargs):
    normalized = normalize_language_code(language_code)
    options = TRANSLATIONS.get(key)
    if not options:
        template = key
    else:
        template = options.get(normalized) or options.get(DEFAULT_LANGUAGE) or key

    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError, ValueError) :
            return template
    return template


def translate_text(language_code, text):
    source_text = str(text or "")
    canonical = LOCALIZED_TEXT_TO_SOURCE.get(source_text, source_text)
    options = SOURCE_TEXT_TRANSLATIONS.get(canonical)
    if not options:
        return _translate_compound_text(language_code, source_text)
    normalized = normalize_language_code(language_code)
    return options.get(normalized) or options.get(DEFAULT_LANGUAGE) or canonical


def translate_rich_text(language_code, text):
    source_text = str(text or "")
    if not source_text:
        return source_text
    if "<" not in source_text or ">" not in source_text:
        return translate_text(language_code, source_text)

    translated_parts = []
    for part in _HTML_TAG_SPLIT_PATTERN.split(source_text):
        if not part:
            continue
        if _HTML_TAG_SPLIT_PATTERN.fullmatch(part):
            translated_parts.append(part)
            continue
        translated_parts.append(_translate_compound_text(language_code, part))
    return "".join(translated_parts)


_COLON_LABEL_PATTERN = re.compile(r"^(?P<label>[^:\n]{1,80}?)(?P<sep>:\s*)(?P<rest>.+)$")
_TRAILING_SUFFIX_PATTERN = re.compile(r"^(?P<label>.+?)(?P<suffix>\s+\([^)]*\))$")
_SEGMENT_SPLIT_PATTERN = re.compile(r"(\s*\|\s*)")
_HTML_TAG_SPLIT_PATTERN = re.compile(r"(<[^>]+>)")


def _translate_exact_text(language_code, text):
    source_text = str(text or "")
    canonical = LOCALIZED_TEXT_TO_SOURCE.get(source_text, source_text)
    options = SOURCE_TEXT_TRANSLATIONS.get(canonical)
    if not options:
        return source_text, False
    normalized = normalize_language_code(language_code)
    translated = options.get(normalized) or options.get(DEFAULT_LANGUAGE) or canonical
    return translated, True


def _translate_compound_segment(language_code, text):
    source_text = str(text or "")
    translated, found = _translate_exact_text(language_code, source_text)
    if found:
        return translated

    if "|" in source_text:
        parts = _SEGMENT_SPLIT_PATTERN.split(source_text)
        translated_parts = []
        changed = False
        for part in parts:
            if _SEGMENT_SPLIT_PATTERN.fullmatch(part or ""):
                translated_parts.append(part)
                continue
            translated_part = _translate_compound_segment(language_code, part)
            translated_parts.append(translated_part)
            changed = changed or translated_part != part
        if changed:
            return "".join(translated_parts)

    suffix_match = _TRAILING_SUFFIX_PATTERN.match(source_text)
    if suffix_match:
        translated_label, label_found = _translate_exact_text(language_code, suffix_match.group("label"))
        if label_found:
            return f"{translated_label}{suffix_match.group('suffix')}"

    colon_match = _COLON_LABEL_PATTERN.match(source_text)
    if colon_match:
        translated_label, label_found = _translate_exact_text(language_code, colon_match.group("label").strip())
        if label_found:
            rest = colon_match.group("rest")
            translated_rest, rest_found = _translate_exact_text(language_code, rest.strip())
            if rest_found:
                rest = translated_rest
            return f"{translated_label}{colon_match.group('sep')}{rest}"

    return source_text


def _translate_compound_text(language_code, text):
    source_text = str(text or "")
    if not source_text:
        return source_text

    if "\n" in source_text:
        lines = source_text.split("\n")
        translated_lines = [_translate_compound_segment(language_code, line) for line in lines]
        translated = "\n".join(translated_lines)
        if translated != source_text:
            return translated

    return _translate_compound_segment(language_code, source_text)


def _sync_runtime_source_text(current_text, stored_source, previous_language):
    current = str(current_text or "")
    if not current and stored_source is None:
        return current, None

    canonical_current = LOCALIZED_TEXT_TO_SOURCE.get(current, current)
    source = str(stored_source) if stored_source not in (None, "") else None
    if source is None:
        source = canonical_current
    elif previous_language:
        expected_previous = translate_text(previous_language, source)
        if current != expected_previous:
            source = canonical_current
    return current, source


def _translate_runtime_attr(obj, language_code, previous_language, property_name, getter_name, setter_name, translator=None):
    getter = getattr(obj, getter_name, None)
    setter = getattr(obj, setter_name, None)
    if not callable(getter) or not callable(setter):
        return

    try:
        current_value = getter()
    except (TypeError, ValueError, AttributeError):
        return

    if current_value is None:
        return

    current_text, source_text = _sync_runtime_source_text(
        current_value,
        obj.property(property_name) if hasattr(obj, "property") else None,
        previous_language,
    )
    if source_text is None:
        return

    if hasattr(obj, "setProperty"):
        obj.setProperty(property_name, source_text)

    translate_fn = translator or translate_text
    translated = translate_fn(language_code, source_text)
    if translated != current_text:
        try:
            setter(translated)
        except Exception:
            pass


def _translate_combo_items(combo, language_code, previous_language, item_role):
    count_getter = getattr(combo, "count", None)
    item_text = getattr(combo, "itemText", None)
    item_data = getattr(combo, "itemData", None)
    set_item_data = getattr(combo, "setItemData", None)
    set_item_text = getattr(combo, "setItemText", None)
    if not all(callable(method) for method in (count_getter, item_text, item_data, set_item_data, set_item_text)):
        return

    try:
        count = int(count_getter())
    except Exception:
        return

    for index in range(count):
        try:
            current_text = item_text(index)
            stored_source = item_data(index, item_role)
        except (TypeError, ValueError, IndexError):
            continue
        current_text, source_text = _sync_runtime_source_text(current_text, stored_source, previous_language)
        if source_text is None:
            continue
        try:
            set_item_data(index, source_text, item_role)
            translated = translate_text(language_code, source_text)
            if translated != current_text:
                set_item_text(index, translated)
        except Exception:
            continue


def _translate_tab_titles(tab_widget, language_code, previous_language):
    count_getter = getattr(tab_widget, "count", None)
    tab_text = getattr(tab_widget, "tabText", None)
    set_tab_text = getattr(tab_widget, "setTabText", None)
    if not all(callable(method) for method in (count_getter, tab_text, set_tab_text)):
        return

    try:
        count = int(count_getter())
    except Exception:
        return

    stored_sources = list(tab_widget.property("_i18n_source_tab_titles") or [])
    if len(stored_sources) < count:
        stored_sources.extend([None] * (count - len(stored_sources)))

    for index in range(count):
        try:
            current_text = tab_text(index)
        except Exception:
            continue
        current_text, source_text = _sync_runtime_source_text(current_text, stored_sources[index], previous_language)
        stored_sources[index] = source_text
        if source_text is None:
            continue
        translated = translate_text(language_code, source_text)
        if translated != current_text:
            try:
                set_tab_text(index, translated)
            except Exception:
                pass

    tab_widget.setProperty("_i18n_source_tab_titles", stored_sources)


def _translate_table_headers(table, language_code, previous_language, item_role):
    column_count = getattr(table, "columnCount", None)
    row_count = getattr(table, "rowCount", None)
    horizontal_header_item = getattr(table, "horizontalHeaderItem", None)
    vertical_header_item = getattr(table, "verticalHeaderItem", None)
    if callable(column_count) and callable(horizontal_header_item):
        try:
            total_columns = int(column_count())
        except Exception:
            total_columns = 0
        for index in range(total_columns):
            item = horizontal_header_item(index)
            if item is None:
                continue
            current_text, source_text = _sync_runtime_source_text(item.text(), item.data(item_role), previous_language)
            if source_text is None:
                continue
            item.setData(item_role, source_text)
            translated = translate_text(language_code, source_text)
            if translated != current_text:
                item.setText(translated)
    if callable(row_count) and callable(vertical_header_item):
        try:
            total_rows = int(row_count())
        except Exception:
            total_rows = 0
        for index in range(total_rows):
            item = vertical_header_item(index)
            if item is None:
                continue
            current_text, source_text = _sync_runtime_source_text(item.text(), item.data(item_role), previous_language)
            if source_text is None:
                continue
            item.setData(item_role, source_text)
            translated = translate_text(language_code, source_text)
            if translated != current_text:
                item.setText(translated)


def _translate_table_items(table, language_code, previous_language, item_role):
    row_count = getattr(table, "rowCount", None)
    column_count = getattr(table, "columnCount", None)
    item_getter = getattr(table, "item", None)
    if not all(callable(method) for method in (row_count, column_count, item_getter)):
        return

    try:
        total_rows = int(row_count())
        total_columns = int(column_count())
    except Exception:
        return

    for row_index in range(total_rows):
        for column_index in range(total_columns):
            item = item_getter(row_index, column_index)
            if item is None:
                continue
            current_text, source_text = _sync_runtime_source_text(item.text(), item.data(item_role), previous_language)
            if source_text is None:
                continue
            item.setData(item_role, source_text)
            translated = translate_text(language_code, source_text)
            if translated != current_text:
                item.setText(translated)


def _translate_tree_headers(tree, language_code, previous_language):
    column_count = getattr(tree, "columnCount", None)
    header_text = getattr(tree, "headerItem", None)
    if not callable(column_count) or not callable(header_text):
        return

    try:
        total_columns = int(column_count())
    except Exception:
        return

    header_item = header_text()
    if header_item is None:
        return

    stored_sources = list(tree.property("_i18n_source_tree_headers") or [])
    if len(stored_sources) < total_columns:
        stored_sources.extend([None] * (total_columns - len(stored_sources)))

    for index in range(total_columns):
        current_text, source_text = _sync_runtime_source_text(header_item.text(index), stored_sources[index], previous_language)
        stored_sources[index] = source_text
        if source_text is None:
            continue
        translated = translate_text(language_code, source_text)
        if translated != current_text:
            try:
                header_item.setText(index, translated)
            except (TypeError, AttributeError, ValueError):
                pass

    tree.setProperty("_i18n_source_tree_headers", stored_sources)


def _translate_tree_item(item, language_code, previous_language, item_role):
    column_count = getattr(item, "columnCount", None)
    if not callable(column_count):
        return

    try:
        total_columns = int(column_count())
    except Exception:
        total_columns = 0

    for index in range(total_columns):
        try:
            current_text = item.text(index)
            stored_source = item.data(index, item_role)
        except Exception:
            continue
        current_text, source_text = _sync_runtime_source_text(current_text, stored_source, previous_language)
        if source_text is None:
            continue
        try:
            item.setData(index, item_role, source_text)
            translated = translate_text(language_code, source_text)
            if translated != current_text:
                item.setText(index, translated)
        except Exception:
            continue

    child_count = getattr(item, "childCount", None)
    child_getter = getattr(item, "child", None)
    if not callable(child_count) or not callable(child_getter):
        return

    try:
        total_children = int(child_count())
    except Exception:
        total_children = 0

    for child_index in range(total_children):
        child_item = child_getter(child_index)
        if child_item is not None:
            _translate_tree_item(child_item, language_code, previous_language, item_role)


def _translate_tree_items(tree, language_code, previous_language, item_role):
    top_level_count = int(getattr(tree, "topLevelItemCount", 0))
    top_level_item = getattr(tree, "topLevelItem", 0)
    if not callable(top_level_count) or not callable(top_level_item):
        return

    try:
        total_items = int(top_level_count())
    except Exception:
        return

    for index in range(total_items):
        item = top_level_item(index)
        if item is not None:
            _translate_tree_item(item, language_code, previous_language, item_role)


def apply_runtime_translations(root, language_code, previous_language=None):
    try:
        from PySide6.QtCore import QObject, Qt
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import (
            QAbstractButton,
            QComboBox,
            QDockWidget,
            QGroupBox,
            QLabel,
            QMenu,
            QTabWidget,
            QTableWidget,
            QTextBrowser,
            QTreeWidget,
            QWidget,
        )
    except (ImportError, ModuleNotFoundError):
        return

    if root is None:
        return

    normalized = normalize_language_code(language_code)
    previous = normalize_language_code(previous_language) if previous_language else None
    item_role = int(Qt.ItemDataRole.UserRole) + 4096

    objects = [root]
    find_children = getattr(root, "findChildren", None)
    if callable(find_children):
        try:
            objects.extend(root.findChildren(QObject))
        except Exception:
            pass

    seen = set()
    for obj in objects:
        marker = id(obj)
        if marker in seen:
            continue
        seen.add(marker)

        if isinstance(obj, (QLabel, QAbstractButton, QAction)):
            _translate_runtime_attr(obj, normalized, previous, "_i18n_source_text", "text", "setText")

        if isinstance(obj, QTextBrowser):
            _translate_runtime_attr(
                obj,
                normalized,
                previous,
                "_i18n_source_html",
                "toHtml",
                "setHtml",
                translator=translate_rich_text,
            )

        if isinstance(obj, (QWidget, QDockWidget)):
            _translate_runtime_attr(obj, normalized, previous, "_i18n_source_window_title", "windowTitle", "setWindowTitle")
            _translate_runtime_attr(obj, normalized, previous, "_i18n_source_tooltip", "toolTip", "setToolTip")
            _translate_runtime_attr(obj, normalized, previous, "_i18n_source_placeholder", "placeholderText", "setPlaceholderText")

        if isinstance(obj, QAction):
            _translate_runtime_attr(obj, normalized, previous, "_i18n_source_tooltip", "toolTip", "setToolTip")

        if isinstance(obj, (QMenu, QGroupBox)):
            _translate_runtime_attr(obj, normalized, previous, "_i18n_source_title", "title", "setTitle")

        if isinstance(obj, QComboBox):
            _translate_combo_items(obj, normalized, previous, item_role)

        if isinstance(obj, QTabWidget):
            _translate_tab_titles(obj, normalized, previous)

        if isinstance(obj, QTableWidget):
            _translate_table_headers(obj, normalized, previous, item_role)
            _translate_table_items(obj, normalized, previous, item_role)

        if isinstance(obj, QTreeWidget):
            _translate_tree_headers(obj, normalized, previous)
            _translate_tree_items(obj, normalized, previous, item_role)

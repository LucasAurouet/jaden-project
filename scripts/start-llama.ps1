<#
.SYNOPSIS
    Lance les deux llama-server de Jaden (chat + embeddings) pour le développement.

.DESCRIPTION
    Démarre les deux instances en arrière-plan, attend qu'elles aient chargé leur
    modèle, puis les surveille. Ctrl+C (ou l'arrêt de l'une d'elles) arrête les deux.
    Les journaux sont écrits dans logs/.

    Configuration lue dans le .env à la racine du projet :
        LLAMA_SERVER         exécutable llama-server (défaut : llama-server, via le PATH)
        LLAMA_CHAT_MODEL     chemin du .gguf du LLM de chat            (obligatoire)
        LLAMA_EMBED_MODEL    chemin du .gguf du modèle d'embeddings     (obligatoire)
        LLAMA_CHAT_CTX       contexte du LLM de chat, défaut 16384

    Les ports sont ceux de LLM_BASE_URL et EMBEDDING_BASE_URL, que le backend
    utilise pour joindre les serveurs : ces URL doivent donc désigner la machine
    locale. Si elles pointent ailleurs (API Mistral, autre machine), ce script
    n'a rien à lancer.

    Pas destiné à la production : il faut une session ouverte et le terminal reste occupé.

.EXAMPLE
    .\scripts\start-llama.ps1
#>

$ErrorActionPreference = "Stop"

$Root = Split-Path $PSScriptRoot -Parent
$LogDir = Join-Path $Root "logs"

# ─── Configuration (.env) ───────────────────────────────────────────────────

$DotEnv = @{}
$DotEnvFile = Join-Path $Root ".env"
if (Test-Path $DotEnvFile) {
    foreach ($line in Get-Content $DotEnvFile -Encoding UTF8) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
            $DotEnv[$Matches[1]] = $Matches[2].Trim('"', "'")
        }
    }
}

function Get-Setting([string]$Name, [string]$Default = $null) {
    if ($DotEnv.ContainsKey($Name) -and $DotEnv[$Name]) { return $DotEnv[$Name] }
    if ($null -ne $Default) { return $Default }
    throw "$Name manquant dans $DotEnvFile"
}

$LlamaServer = Get-Setting "LLAMA_SERVER" "llama-server"
$ChatModel   = Get-Setting "LLAMA_CHAT_MODEL"
$EmbedModel  = Get-Setting "LLAMA_EMBED_MODEL"
$ChatCtx     = Get-Setting "LLAMA_CHAT_CTX" "16384"

# Port d'écoute déduit de l'URL utilisée par le backend (mêmes défauts que config.py).
function Get-LocalPort([string]$UrlSetting, [string]$Default) {
    $url = Get-Setting $UrlSetting $Default
    $uri = $null
    if (-not [Uri]::TryCreate($url, [UriKind]::Absolute, [ref]$uri)) {
        throw "$UrlSetting n'est pas une URL valide : $url"
    }
    if (-not $uri.IsLoopback) {
        throw "$UrlSetting ($url) ne désigne pas cette machine : il n'y a pas de llama-server local à lancer pour elle."
    }
    return [string]$uri.Port
}

$ChatPort  = Get-LocalPort "LLM_BASE_URL" "http://127.0.0.1:8080"
$EmbedPort = Get-LocalPort "EMBEDDING_BASE_URL" "http://127.0.0.1:8082"
if ($ChatPort -eq $EmbedPort) {
    throw "LLM_BASE_URL et EMBEDDING_BASE_URL utilisent le même port ($ChatPort) : il faut un port par llama-server."
}

foreach ($model in $ChatModel, $EmbedModel) {
    if (-not (Test-Path $model)) { throw "Modèle introuvable : $model" }
}
if (-not (Get-Command $LlamaServer -ErrorAction SilentlyContinue)) {
    throw "llama-server introuvable ('$LlamaServer') : ajoutez-le au PATH ou renseignez LLAMA_SERVER."
}

# ─── Instances ──────────────────────────────────────────────────────────────

$Servers = @(
    @{
        Name = "chat"
        Port = $ChatPort
        # --jinja : indispensable aux tools.
        Args = @("-m", $ChatModel, "--host", "127.0.0.1", "--port", $ChatPort,
                 "-ngl", "99", "-c", $ChatCtx, "--jinja")
    },
    @{
        Name = "embed"
        Port = $EmbedPort
        # -ub : chaque passage doit tenir entier dans un micro-lot.
        Args = @("-m", $EmbedModel, "--host", "127.0.0.1", "--port", $EmbedPort,
                 "-ngl", "99", "--embedding", "--pooling", "cls",
                 "-c", "8192", "-b", "2048", "-ub", "2048")
    }
)

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# Start-Process concatène les arguments sans guillemets : on protège ceux
# qui contiennent des espaces (chemins de modèles).
function Format-Args([string[]]$Arguments) {
    $Arguments | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }
}

function Stop-Servers {
    foreach ($s in $Servers) {
        if ($s.Process -and -not $s.Process.HasExited) {
            Write-Host "Arrêt de llama-server ($($s.Name))…"
            Stop-Process -Id $s.Process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

try {
    foreach ($s in $Servers) {
        $log = Join-Path $LogDir "llama-$($s.Name)"
        $s.Process = Start-Process -FilePath $LlamaServer -ArgumentList (Format-Args $s.Args) `
            -NoNewWindow -PassThru `
            -RedirectStandardOutput "$log.out.log" -RedirectStandardError "$log.err.log"
        Write-Host "llama-server ($($s.Name)) lancé sur le port $($s.Port), PID $($s.Process.Id) — journaux : $log.*.log"
    }

    # /health renvoie 503 tant que le modèle charge, 200 une fois prêt.
    $deadline = (Get-Date).AddMinutes(5)
    foreach ($s in $Servers) {
        while ($true) {
            if ($s.Process.HasExited) {
                throw "llama-server ($($s.Name)) s'est arrêté au démarrage : voir logs\llama-$($s.Name).err.log"
            }
            try {
                Invoke-WebRequest "http://127.0.0.1:$($s.Port)/health" -UseBasicParsing -TimeoutSec 2 | Out-Null
                break
            } catch {
                if ((Get-Date) -gt $deadline) { throw "llama-server ($($s.Name)) n'est pas prêt après 5 minutes." }
                Start-Sleep -Seconds 1
            }
        }
        Write-Host "llama-server ($($s.Name)) prêt." -ForegroundColor Green
    }

    Write-Host "Les deux instances tournent. Ctrl+C pour tout arrêter."
    while ($true) {
        foreach ($s in $Servers) {
            if ($s.Process.HasExited) {
                throw "llama-server ($($s.Name)) s'est arrêté (code $($s.Process.ExitCode)) : voir logs\llama-$($s.Name).err.log"
            }
        }
        Start-Sleep -Seconds 2
    }
}
finally {
    # Exécuté aussi sur Ctrl+C.
    Stop-Servers
}

<#
.SYNOPSIS
    Task runner for the RodGrowth_database pipeline.

.DESCRIPTION
    Provides shortcuts for common development tasks: install, run, test,
    lint, clean. Loads the appropriate schema configuration based on the
    -Schema parameter (test or prod).

.PARAMETER Task
    The task to execute. One of: install, run, test, lint, clean, help.

.PARAMETER InputFile
    Path to the raw machine Excel file.
    Default: data\raw_machine_output.xlsx

.PARAMETER OutputFile
    Path for the cleaned output file.
    Default: output\clean.csv

.PARAMETER Reports
    Directory for validation report CSVs.
    Default: output\reports

.PARAMETER Format
    Output format: csv or json.
    Default: csv

.PARAMETER Variants
    PS variant resolution strategy: none, base, or variant.
        none    = report only, do not remove (default)
        base    = keep 'XX01', drop 'XX01_naklon'
        variant = keep 'XX01_naklon', drop 'XX01'

.PARAMETER Schema
    Which schema configuration to load: test or prod.
    Default: test

.EXAMPLE
    .\run.ps1 install
    Installs the project in editable mode with development dependencies.

.EXAMPLE
    .\run.ps1 run
    Runs the pipeline with default paths and the test schema.

.EXAMPLE
    .\run.ps1 run -Schema prod -InputFile data\real_data.xlsx
    Runs the pipeline against production data using the prod schema.

.EXAMPLE
    .\run.ps1 run -Variants base -Format json
    Runs the pipeline, keeps base PS names (drops _naklon variants),
    and exports as JSON.

.EXAMPLE
    .\run.ps1 test
    Runs the full pytest test suite.

.EXAMPLE
    .\run.ps1 clean
    Removes output and Python cache directories. 
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('install', 'run', 'test', 'lint', 'clean', 'help')]
    [string]$Task = 'help',

    [string]$InputFile = 'data\Databaze_rustu_DD-test.xlsx',
    [string]$OutputFile = 'output\clean.csv',
    [string]$Reports = 'output\reports',

    [ValidateSet('csv', 'json')]
    [string]$Format = 'csv',

    [ValidateSet('none', 'base', 'variant')]
    [string]$Variants = 'none',

    [ValidateSet('test', 'prod')]
    [string]$Schema = 'test'
)

$ErrorActionPreference = 'Stop'

function Invoke-Install {
    Write-Host "Installing project in editable mode with dev dependencies..." -ForegroundColor Cyan
    pip install -e ".[dev]"
}

function Invoke-Run {
    $schemaPath = "config\schema.$Schema.yaml"

    if (-not (Test-Path $schemaPath)) {
        Write-Error "Schema file not found: $schemaPath"
        return
    }

    if (-not (Test-Path $InputFile)) {
        Write-Error "Input file not found: $InputFile"
        return
    }

    Write-Host ""
    Write-Host "Running pipeline..." -ForegroundColor Cyan
    Write-Host "  Schema:   $schemaPath"
    Write-Host "  Input:    $InputFile"
    Write-Host "  Output:   $OutputFile"
    Write-Host "  Reports:  $Reports"
    Write-Host "  Format:   $Format"
    Write-Host "  Variants: $Variants"
    Write-Host ""

    $env:RODGROWTH_SCHEMA = $schemaPath
    python -m src.main `
        --input $InputFile `
        --output $OutputFile `
        --report-dir $Reports `
        --format $Format `
        --resolve-variants $Variants
}

function Invoke-Test {
    Write-Host "Running pytest..." -ForegroundColor Cyan
    pytest
}

function Invoke-Lint {
    Write-Host "Running ruff..." -ForegroundColor Cyan
    ruff check src/ tests/
}

function Invoke-Clean {
    Write-Host "Removing output and cache directories..." -ForegroundColor Cyan
    $paths = @(
        'output',
        '__pycache__',
        '.pytest_cache',
        '.ruff_cache',
        'src\__pycache__',
        'tests\__pycache__',
        'config\__pycache__',
        'build',
        'rodgrowth_database.egg-info'
    )
    foreach ($path in $paths) {
        if (Test-Path $path) {
            Remove-Item -Recurse -Force $path
            Write-Host "  Removed: $path"
        }
    }
    Write-Host "Clean complete." -ForegroundColor Green
}

function Show-Help {
    Write-Host ""
    Write-Host "RodGrowth_database -- task runner" -ForegroundColor Green
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\run.ps1 <task> [parameters]"
    Write-Host ""
    Write-Host "Tasks:" -ForegroundColor Yellow
    Write-Host "  install   Install project in editable mode (pip install -e `".[dev]`")"
    Write-Host "  run       Run the pipeline"
    Write-Host "  test      Run pytest test suite"
    Write-Host "  lint      Run ruff linter on src/ and tests/"
    Write-Host "  clean     Remove output and cache directories"
    Write-Host "  help      Show this help"
    Write-Host ""
    Write-Host "Parameters for 'run':" -ForegroundColor Yellow
    Write-Host "  -Schema <test|prod>             Which schema config to load (default: test)"
    Write-Host "  -InputFile <path>               Input Excel file"
    Write-Host "  -OutputFile <path>              Output file"
    Write-Host "  -Reports <path>                 Reports directory"
    Write-Host "  -Format <csv|json>              Output format"
    Write-Host "  -Variants <none|base|variant>   PS variant resolution"
    Write-Host "                                    none    = report only (default)"
    Write-Host "                                    base    = keep 'XX01', drop 'XX01_naklon'"
    Write-Host "                                    variant = keep 'XX01_naklon', drop 'XX01'"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host "  .\run.ps1 install"
    Write-Host "  .\run.ps1 run"
    Write-Host "  .\run.ps1 run -Schema prod -InputFile data\real.xlsx"
    Write-Host "  .\run.ps1 run -Variants base -Format json"
    Write-Host "  .\run.ps1 test"
    Write-Host "  .\run.ps1 clean"
    Write-Host ""
}

switch ($Task) {
    'install' { Invoke-Install }
    'run' { Invoke-Run }
    'test' { Invoke-Test }
    'lint' { Invoke-Lint }
    'clean' { Invoke-Clean }
    'help' { Show-Help }
}
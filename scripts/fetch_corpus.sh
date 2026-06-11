#!/usr/bin/env bash
# fetch_corpus.sh - Recuperation d'un corpus public a licence ouverte pour le TP RAG.
#
# Sources :
#   - CERT-FR  : avis de securite HTML + JSON.
#   - CNIL     : guides RGPD PDF.
#   - data.gouv: jeux de donnees publics via API.
#
# Usage :
#   bash scripts/fetch_corpus.sh
#   PROFILE=open bash scripts/fetch_corpus.sh
#   PROFILE=cert N_AVIS=40 bash scripts/fetch_corpus.sh
#
# Pour le projet A, le profil recommande est PROFILE=open. Les fichiers
# telecharges sont places dans corpus/raw/ et ne doivent pas etre committes.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_DIR="${HERE}/corpus/raw"
mkdir -p "${RAW_DIR}/cert-fr" "${RAW_DIR}/cnil" "${RAW_DIR}/data-gouv"

PROFILE="${PROFILE:-open}"
N_AVIS="${N_AVIS:-30}"

CURL=(curl -fSL --retry 3 --retry-delay 2 --connect-timeout 15 -A "Mozilla/5.0")

log()  { printf '\033[0;36m[fetch]\033[0m %s\n' "$*"; }
warn() { printf '\033[0;33m[warn ]\033[0m %s\n' "$*" >&2; }

is_valid_file() {
  local file="$1"
  local ext="${file##*.}"

  if [ ! -s "$file" ]; then
    return 1
  fi

  case "$ext" in
    pdf)
      head -c 5 "$file" | grep -q "%PDF-"
      ;;
    json)
      head -c 1 "$file" | grep -q '[{\[]'
      ;;
    csv|txt|html)
      ! head -c 100 "$file" | grep -qi "<!doctype html"
      ;;
    *)
      return 0
      ;;
  esac
}

fetch_cert() {
  log "CERT-FR : recuperation du flux d'avis..."
  local feed
  feed="$(mktemp)"

  if ! "${CURL[@]}" "https://www.cert.ssi.gouv.fr/avis/feed/" -o "${feed}"; then
    warn "Flux CERT-FR injoignable, on saute cette source."
    rm -f "${feed}"
    return 0
  fi

  local ids
  ids="$(grep -oE 'CERTFR-[0-9]{4}-AVI-[0-9]{4}' "${feed}" | sort -u | head -n "${N_AVIS}")"
  rm -f "${feed}"

  local count=0
  for id in ${ids}; do
    local base="https://www.cert.ssi.gouv.fr/avis/${id}"

    if "${CURL[@]}" "${base}/json/" -o "${RAW_DIR}/cert-fr/${id}.json" 2>/dev/null; then
      count=$((count + 1))
    else
      warn "JSON indisponible pour ${id}"
    fi

    "${CURL[@]}" "${base}/" -o "${RAW_DIR}/cert-fr/${id}.html" 2>/dev/null \
      || warn "HTML indisponible pour ${id}"
  done

  log "CERT-FR : ${count} avis recuperes dans corpus/raw/cert-fr/"
}

fetch_cnil() {
  log "CNIL : recuperation des guides RGPD (PDF)..."
  local urls=(
    "https://www.cnil.fr/sites/default/files/atoms/files/cnil_guide_securite_des_donnees_personnelles-2023.pdf"
    "https://www.cnil.fr/sites/default/files/atoms/files/bpi-cnil-rgpd_guide-tpe-pme.pdf"
    "https://www.cnil.fr/sites/default/files/atoms/files/rgpd-guide_sous-traitant-cnil.pdf"
  )

  local count=0
  for url in "${urls[@]}"; do
    local name
    name="$(basename "${url}")"
    local out="${RAW_DIR}/cnil/${name}"

    if "${CURL[@]}" "${url}" -o "${out}" 2>/dev/null && is_valid_file "${out}"; then
      count=$((count + 1))
    else
      warn "PDF invalide ou indisponible : ${url}"
      rm -f "${out}"
    fi
  done

  log "CNIL : ${count} guides recuperes dans corpus/raw/cnil/"
}

fetch_open() {
  log "data.gouv.fr : recherche de jeux de donnees..."
  local query="${DATA_QUERY:-intelligence artificielle}"
  local api="https://www.data.gouv.fr/api/1/datasets/?page_size=10&q=${query// /%20}"
  local meta
  meta="$(mktemp)"

  if ! "${CURL[@]}" "${api}" -o "${meta}"; then
    warn "API data.gouv injoignable, on saute cette source."
    rm -f "${meta}"
    return 0
  fi

  local urls
  urls="$(grep -oE 'https://[^" ]+\.(pdf|csv|json|txt)' "${meta}" | sort -u | head -n 10)"
  rm -f "${meta}"

  local count=0
  for url in ${urls}; do
    local name
    name="$(basename "${url}" | tr -cd 'A-Za-z0-9._-')"
    [ -z "${name}" ] && name="resource_${count}.bin"

    local out="${RAW_DIR}/data-gouv/${name}"

    if "${CURL[@]}" "${url}" -o "${out}" 2>/dev/null && is_valid_file "${out}"; then
      count=$((count + 1))
      log "OK : ${name}"
    else
      warn "Ressource invalide ignoree : ${url}"
      rm -f "${out}"
    fi

    if [ "${count}" -ge 5 ]; then
      break
    fi
  done

  log "data.gouv : ${count} ressources valides recuperees dans corpus/raw/data-gouv/"
}

case "${PROFILE}" in
  cert)  fetch_cert ;;
  cnil)  fetch_cnil ;;
  open)  fetch_open ;;
  mixte) fetch_cert; fetch_cnil; fetch_open ;;
  *)     warn "PROFILE inconnu : ${PROFILE} (mixte|cert|cnil|open)"; exit 1 ;;
esac

total="$(find "${RAW_DIR}" -type f | wc -l | tr -d ' ')"
log "Termine. ${total} fichiers dans corpus/raw/ (gitignore, non committe)."
log "Le corpus seed committe reste dans corpus/seed/ pour un demarrage offline."

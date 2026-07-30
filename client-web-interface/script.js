// Budget de bout en bout :
// AI Service 60 s < Nginx 75 s < navigateur 90 s.
const REQUEST_TIMEOUT_MS = 90000;
const HEALTH_TIMEOUT_MS = 4000;
const CATALOG_TIMEOUT_MS = 12000;
const MAX_TEXTAREA_HEIGHT = 150;

const TIMEOUT_MESSAGE = "Le service d'assistance a mis trop de temps à " +
    "répondre. Réessayez avec une question plus simple.";
const RESEAU_MESSAGE = "Impossible de contacter le service d'assistance. " +
    "Vérifiez votre connexion, puis réessayez.";

const form = document.getElementById("query-form");
const input = document.getElementById("question");
const submitButton = document.getElementById("submit-button");
const conversation = document.getElementById("conversation");
const welcome = document.getElementById("welcome");
const messages = document.getElementById("messages");
const assistantTemplate = document.getElementById(
    "assistant-message-template"
);
const userTemplate = document.getElementById("user-message-template");
const connectionStatus = document.getElementById("connection-status");
const statusLabel = connectionStatus.querySelector(".status-label");
const themeToggle = document.getElementById("theme-toggle");
const websocketConfiguration = document.querySelector(
    'meta[name="cwi-websocket-url"]'
);
const productDialog = document.getElementById("product-dialog");
const productDialogImage = document.getElementById("product-dialog-image");
const productDialogTitle = document.getElementById("product-dialog-title");
const productDialogBrand = document.getElementById("product-dialog-brand");
const productDialogCategory = document.getElementById(
    "product-dialog-category"
);
const productDialogPrice = document.getElementById("product-dialog-price");
const productDialogStock = document.getElementById("product-dialog-stock");
const productDialogSku = document.getElementById("product-dialog-sku");
const productDialogId = document.getElementById("product-dialog-id");
const productDialogDescription = document.getElementById(
    "product-dialog-description"
);
const productDialogSupplier = document.getElementById(
    "product-dialog-supplier"
);

let socket = null;
let requeteActive = null;
let reconnexion = null;
let productDialogRequest = 0;
const productsByName = new Map();
const productDetailsById = new Map();
const cataloguePromise = chargerCatalogue();

function creerElement(tag, className, text) {
    const element = document.createElement(tag);
    element.className = className;
    if (text !== undefined) {
        element.textContent = text;
    }
    return element;
}

function reglerEtatConnexion(etat, libelle) {
    connectionStatus.dataset.state = etat;
    statusLabel.textContent = libelle;
}

function ajusterZoneTexte() {
    input.style.height = "auto";
    input.style.height = Math.min(
        input.scrollHeight,
        MAX_TEXTAREA_HEIGHT
    ) + "px";
}

function positionnerNouvelEchange(messageUtilisateur) {
    requestAnimationFrame(() => {
        const conversationTop = conversation.getBoundingClientRect().top;
        const messageTop = messageUtilisateur.getBoundingClientRect().top;
        const destination = conversation.scrollTop +
            messageTop - conversationTop - 22;

        conversation.scrollTo({
            top: Math.max(0, destination),
            behavior: "smooth"
        });
    });
}

function ajouterMessageUtilisateur(question) {
    const message = userTemplate.content.firstElementChild.cloneNode(true);
    message.querySelector(".message-content").textContent = question;
    messages.append(message);
    return message;
}

function indicateurEcriture() {
    const indicateur = creerElement("span", "typing-indicator");
    indicateur.setAttribute("aria-label", "L'assistant réfléchit");
    indicateur.append(
        document.createElement("span"),
        document.createElement("span"),
        document.createElement("span")
    );
    return indicateur;
}

function ajouterMessageAssistant() {
    const message = assistantTemplate.content.firstElementChild.cloneNode(true);
    const contenu = message.querySelector(".message-content");
    const etat = message.querySelector(".message-state");
    const listeEtapes = message.querySelector(".message-steps");

    contenu.append(indicateurEcriture());
    etat.textContent = "Analyse de votre demande…";
    messages.append(message);

    return {
        message,
        contenu,
        etat,
        listeEtapes,
        etapes: new Map(),
        texte: "",
        delai: null,
        controleur: null,
        finalise: false
    };
}

function definirEtatAssistant(contexte, texte) {
    contexte.etat.textContent = texte || "";
}

function mettreAJourEtape(contexte, donnees) {
    if (!contexte.listeEtapes || typeof donnees.step !== "string") {
        return;
    }

    let etape = contexte.etapes.get(donnees.step);
    if (!etape) {
        etape = creerElement("li", "message-step");
        etape.append(
            creerElement("span", "step-marker"),
            creerElement("span", "step-label")
        );
        contexte.etapes.set(donnees.step, etape);
        contexte.listeEtapes.append(etape);
    }

    etape.dataset.state = donnees.state || "active";
    etape.querySelector(".step-label").textContent =
        typeof donnees.message === "string"
            ? donnees.message
            : "Traitement en cours…";
    contexte.listeEtapes.hidden = false;
}

// Le WebSocket appelle cette fonction à chaque fragment reçu : le message
// grandit dans la même bulle, sans recréer toute la conversation.
function ajouterFragmentAssistant(contexte, fragment) {
    if (typeof fragment !== "string" || !fragment) {
        return;
    }

    if (!contexte.texte) {
        contexte.contenu.replaceChildren();
        contexte.contenu.classList.add("streaming-copy");
    }

    contexte.texte += fragment;
    contexte.contenu.textContent = contexte.texte;
}

function analyserLigneProduit(ligne) {
    const contenu = ligne.replace(/^•\s*/, "").trim();
    const formats = [
        /^(.*?)\s+[—–-]\s+(\d+)\s+unit[eé]s?$/i,
        /^(.*?),\s*quantit[eé]\s*:?\s*(\d+)$/i
    ];

    for (const format of formats) {
        const correspondance = contenu.match(format);
        if (correspondance) {
            return {
                nom: correspondance[1].trim(),
                quantite: Number(correspondance[2])
            };
        }
    }

    return {nom: contenu, quantite: null};
}

function productNameKey(name) {
    return String(name || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .trim()
        .toLocaleLowerCase("fr");
}

async function chargerCatalogue() {
    try {
        const {response, data} = await fetchJson(
            "/api/products",
            CATALOG_TIMEOUT_MS
        );
        if (!response.ok || !Array.isArray(data.products)) {
            return;
        }

        for (const product of data.products) {
            if (product && product.name) {
                productsByName.set(productNameKey(product.name), product);
            }
        }
    } catch (error) {
        /* Les réponses textuelles restent utilisables sans catalogue. */
    }
}

async function fetchJson(url, timeoutMs) {
    const controller = new AbortController();
    const timeout = setTimeout(
        () => controller.abort(),
        timeoutMs
    );

    try {
        const response = await fetch(url, {
            signal: controller.signal
        });
        const data = await response.json().catch(() => null) || {};
        return {response, data};
    } finally {
        clearTimeout(timeout);
    }
}

function productImageUrl(product) {
    const sku = product && typeof product.sku === "string"
        ? product.sku.trim()
        : "";
    if (!/^[A-Za-z0-9-]+$/.test(sku)) {
        return "";
    }
    return "images/products/" + encodeURIComponent(sku) + ".png";
}

function configureProductImage(image, product, altText) {
    const imageUrl = productImageUrl(product);
    image.hidden = !imageUrl;
    image.onerror = () => {
        image.hidden = true;
    };

    if (imageUrl) {
        image.src = imageUrl;
        image.alt = altText || "";
    } else {
        image.removeAttribute("src");
        image.alt = "";
    }
}

function formatProductPrice(product) {
    if (!product || !Number.isFinite(Number(product.unit_price))) {
        return "Non précisé";
    }

    try {
        return new Intl.NumberFormat("fr-FR", {
            style: "currency",
            currency: product.currency || "USD"
        }).format(Number(product.unit_price));
    } catch (error) {
        return Number(product.unit_price).toFixed(2) + " " +
            (product.currency || "");
    }
}

function setDialogTag(element, value) {
    const text = typeof value === "string" ? value.trim() : "";
    element.textContent = text;
    element.hidden = !text;
}

function fillProductDialog(product, quantity, loadingDescription) {
    const productName = product.name || "Produit";
    productDialogTitle.textContent = productName;
    configureProductImage(
        productDialogImage,
        product,
        "Image de " + productName
    );
    setDialogTag(productDialogBrand, product.brand);
    setDialogTag(productDialogCategory, product.category);
    productDialogPrice.textContent = formatProductPrice(product);
    productDialogStock.textContent = Number.isFinite(quantity)
        ? quantity + (quantity !== 1 ? " unités" : " unité")
        : "Non précisé";
    productDialogSku.textContent = product.sku || "Non précisé";
    productDialogId.textContent = product.id !== undefined
        ? String(product.id)
        : "Non précisé";
    productDialogDescription.textContent = product.description ||
        (loadingDescription
            ? "Chargement de la description…"
            : "Description indisponible.");
    productDialogSupplier.textContent = product.supplier_name
        ? "Fourni par " + product.supplier_name
        : "";
}

async function openProductDialog(product, quantity) {
    const requestNumber = ++productDialogRequest;
    const cached = productDetailsById.get(product.id);

    fillProductDialog(cached || product, quantity, !cached);
    if (!productDialog.open) {
        productDialog.showModal();
    }
    if (cached) {
        return;
    }

    try {
        const {response, data} = await fetchJson(
            "/api/products/" + encodeURIComponent(product.id),
            CATALOG_TIMEOUT_MS
        );
        if (!response.ok || !data.product) {
            throw new Error("Détail indisponible");
        }
        productDetailsById.set(product.id, data.product);
        if (requestNumber === productDialogRequest && productDialog.open) {
            fillProductDialog(data.product, quantity, false);
        }
    } catch (error) {
        if (requestNumber === productDialogRequest && productDialog.open) {
            fillProductDialog(product, quantity, false);
        }
    }
}

async function afficherReponseFormatee(answer, conteneur) {
    const lignes = answer
        .split(/\r?\n/)
        .map((ligne) => ligne.trim());
    const lignesProduits = lignes.filter((ligne) => ligne.startsWith("•"));

    conteneur.replaceChildren();

    if (!lignesProduits.length) {
        conteneur.append(creerElement("p", "response-copy", answer));
        return;
    }

    await cataloguePromise;
    const introduction = lignes
        .filter((ligne) => ligne && !ligne.startsWith("•"))
        .join(" ");
    const produits = lignesProduits.map(analyserLigneProduit);
    const resume = creerElement("div", "response-summary");
    const titre = creerElement(
        "p",
        "response-summary-title",
        introduction || "Produits disponibles"
    );
    const compteur = creerElement(
        "span",
        "response-count",
        produits.length + (produits.length !== 1
            ? " références"
            : " référence")
    );

    resume.append(titre, compteur);

    const liste = creerElement("ul", "inventory-list");
    for (const produit of produits) {
        const product = productsByName.get(productNameKey(produit.nom));
        const item = creerElement("li", "inventory-entry");
        const card = creerElement("button", "inventory-item");
        const visual = creerElement("span", "inventory-thumb");
        const copy = creerElement("span", "inventory-copy");
        const name = creerElement("span", "inventory-name", produit.nom);

        card.type = "button";
        copy.append(name);

        if (product) {
            const image = document.createElement("img");
            image.width = 58;
            image.height = 58;
            image.loading = "lazy";
            image.decoding = "async";
            configureProductImage(image, product, "");
            visual.append(image);
            copy.append(
                creerElement("span", "inventory-sku", product.sku || "")
            );
            card.setAttribute(
                "aria-label",
                "Voir la fiche de " + produit.nom
            );
            card.addEventListener("click", () => {
                openProductDialog(product, produit.quantite);
            });
        } else {
            visual.classList.add("inventory-thumb-empty");
            visual.textContent = produit.nom.slice(0, 1).toUpperCase();
            card.disabled = true;
            card.setAttribute(
                "aria-label",
                "Détail indisponible pour " + produit.nom
            );
        }

        if (produit.quantite !== null) {
            card.append(
                visual,
                copy,
                creerElement(
                    "span",
                    "inventory-quantity",
                    produit.quantite + (produit.quantite !== 1
                        ? " unités"
                        : " unité")
                )
            );
        } else {
            card.append(visual, copy);
        }
        item.append(card);
        liste.append(item);
    }

    conteneur.append(resume, liste);
}

async function terminerReponse(contexte, reponseFinale) {
    if (contexte.finalise) {
        return;
    }
    const texteFinal = typeof reponseFinale === "string" &&
        reponseFinale.trim()
        ? reponseFinale.trim()
        : contexte.texte.trim();

    if (!texteFinal) {
        afficherErreur(
            contexte,
            "Le service n'a retourné aucune réponse."
        );
        return;
    }

    contexte.finalise = true;
    contexte.texte = texteFinal;
    contexte.contenu.classList.remove("streaming-copy");
    await afficherReponseFormatee(texteFinal, contexte.contenu);
    definirEtatAssistant(contexte, "");
    finaliserRequete(contexte);
}

function afficherErreur(contexte, message) {
    if (contexte.finalise) {
        return;
    }
    contexte.finalise = true;
    contexte.message.classList.add("message-error");
    contexte.contenu.classList.remove("streaming-copy");
    contexte.contenu.replaceChildren(
        creerElement("p", "response-copy", message || RESEAU_MESSAGE)
    );
    definirEtatAssistant(contexte, "La demande n'a pas abouti.");
    finaliserRequete(contexte);
}

function finaliserRequete(contexte) {
    if (contexte.delai) {
        clearTimeout(contexte.delai);
    }

    if (requeteActive === contexte) {
        requeteActive = null;
    }

    submitButton.disabled = false;
    form.removeAttribute("aria-busy");
    input.focus();
}

// FastAPI renvoie "detail" sous forme de phrase ou de tableau d'erreurs
// Pydantic. Les deux sont ramenés à une phrase lisible.
function messageDepuisDetail(detail) {
    if (typeof detail === "string" && detail.trim()) {
        return detail.trim();
    }

    if (Array.isArray(detail)) {
        const raisons = detail
            .map((erreur) => (erreur && typeof erreur.msg === "string")
                ? erreur.msg.trim()
                : "")
            .filter((raison) => raison);

        if (raisons.length) {
            return "Question refusée : " + raisons.join(" ; ") + ".";
        }
    }

    return "";
}

function messageErreurHttp(status, detail) {
    return messageDepuisDetail(detail) ||
        "Le service d'assistance a répondu une erreur (code " +
        status + ").";
}

async function envoyerParHttp(question, contexte) {
    contexte.controleur = new AbortController();
    contexte.delai = setTimeout(
        () => contexte.controleur.abort(),
        REQUEST_TIMEOUT_MS
    );

    try {
        const apiResponse = await fetch("/api/ask", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({question}),
            signal: contexte.controleur.signal
        });
        const data = await apiResponse.json().catch(() => null) || {};

        if (!apiResponse.ok) {
            throw new Error(
                messageErreurHttp(apiResponse.status, data.detail)
            );
        }
        if (typeof data.answer !== "string" || !data.answer.trim()) {
            throw new Error("Le service n'a retourné aucune réponse.");
        }

        // Le chemin de rendu est le même que pour les futurs fragments WS.
        ajouterFragmentAssistant(contexte, data.answer);
        await terminerReponse(contexte);
    } catch (error) {
        if (error.name === "AbortError") {
            afficherErreur(contexte, TIMEOUT_MESSAGE);
        } else if (error instanceof TypeError) {
            afficherErreur(contexte, RESEAU_MESSAGE);
            reglerEtatConnexion("offline", "Service indisponible");
        } else {
            afficherErreur(contexte, error.message || RESEAU_MESSAGE);
        }
    }
}

function identifiantRequete() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return Date.now().toString(36) + Math.random().toString(36).slice(2);
}

function envoyerParWebSocket(question, contexte) {
    contexte.id = identifiantRequete();
    contexte.delai = setTimeout(() => {
        afficherErreur(contexte, TIMEOUT_MESSAGE);
    }, REQUEST_TIMEOUT_MS);

    socket.send(JSON.stringify({
        type: "question",
        request_id: contexte.id,
        question
    }));
}

async function traiterMessageWebSocket(event) {
    let donnees;

    try {
        donnees = JSON.parse(event.data);
    } catch (error) {
        return;
    }

    const contexte = requeteActive;
    if (!contexte ||
            (donnees.request_id && donnees.request_id !== contexte.id)) {
        return;
    }

    if (donnees.type === "status") {
        mettreAJourEtape(contexte, donnees);
        definirEtatAssistant(
            contexte,
            donnees.state === "active" &&
                typeof donnees.message === "string"
                ? donnees.message
                : ""
        );
        return;
    }

    if (donnees.type === "chunk" || donnees.type === "delta") {
        ajouterFragmentAssistant(
            contexte,
            donnees.content || donnees.delta || ""
        );
        definirEtatAssistant(contexte, "Réponse en direct…");
        return;
    }

    if (donnees.type === "answer") {
        await terminerReponse(contexte, donnees.answer);
        return;
    }

    if (donnees.type === "done") {
        await terminerReponse(contexte);
        return;
    }

    if (donnees.type === "error") {
        afficherErreur(
            contexte,
            messageDepuisDetail(donnees.detail) || RESEAU_MESSAGE
        );
    }
}

function urlWebSocket(valeur) {
    const url = new URL(valeur, window.location.href);
    if (url.protocol === "http:") {
        url.protocol = "ws:";
    } else if (url.protocol === "https:") {
        url.protocol = "wss:";
    }
    return url.toString();
}

async function verifierService() {
    const controleur = new AbortController();
    const delai = setTimeout(() => controleur.abort(), HEALTH_TIMEOUT_MS);

    try {
        const reponse = await fetch("/api/health", {
            signal: controleur.signal
        });
        reglerEtatConnexion(
            reponse.ok ? "online" : "offline",
            reponse.ok ? "Service disponible" : "Service indisponible"
        );
    } catch (error) {
        reglerEtatConnexion("offline", "Service indisponible");
    } finally {
        clearTimeout(delai);
    }
}

function connecterTempsReel() {
    const configuration = websocketConfiguration
        ? websocketConfiguration.content.trim()
        : "";

    if (!configuration || !("WebSocket" in window)) {
        verifierService();
        return;
    }

    if (socket &&
            (socket.readyState === WebSocket.CONNECTING ||
             socket.readyState === WebSocket.OPEN)) {
        return;
    }

    reglerEtatConnexion("checking", "Connexion en direct…");

    try {
        socket = new WebSocket(urlWebSocket(configuration));
    } catch (error) {
        socket = null;
        verifierService();
        return;
    }

    socket.addEventListener("open", () => {
        if (reconnexion) {
            clearTimeout(reconnexion);
            reconnexion = null;
        }
        reglerEtatConnexion("live", "Connecté en direct");
    });
    socket.addEventListener("message", traiterMessageWebSocket);
    socket.addEventListener("close", () => {
        socket = null;
        if (requeteActive) {
            afficherErreur(
                requeteActive,
                "La connexion en direct a été interrompue. Réessayez."
            );
        }

        if (navigator.onLine) {
            verifierService();
            reconnexion = setTimeout(connecterTempsReel, 3000);
        }
    });
    socket.addEventListener("error", () => {
        reglerEtatConnexion("offline", "Connexion interrompue");
    });
}

function envoyerQuestion(question) {
    if (requeteActive) {
        return;
    }

    welcome.hidden = true;
    const messageUtilisateur = ajouterMessageUtilisateur(question);
    const contexte = ajouterMessageAssistant();
    requeteActive = contexte;

    input.value = "";
    ajusterZoneTexte();
    submitButton.disabled = true;
    form.setAttribute("aria-busy", "true");
    positionnerNouvelEchange(messageUtilisateur);

    if (socket && socket.readyState === WebSocket.OPEN) {
        envoyerParWebSocket(question, contexte);
    } else {
        envoyerParHttp(question, contexte);
    }
}

function actualiserBoutonTheme() {
    const sombre = document.documentElement.dataset.theme === "dark";
    themeToggle.setAttribute(
        "aria-label",
        sombre ? "Activer le mode clair" : "Activer le mode sombre"
    );
}

form.addEventListener("submit", (event) => {
    event.preventDefault();
    const question = input.value.trim();

    if (question) {
        envoyerQuestion(question);
    }
});

input.addEventListener("input", ajusterZoneTexte);
input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
    }
});

document.querySelectorAll(".suggestion").forEach((bouton) => {
    bouton.addEventListener("click", () => {
        input.value = bouton.dataset.question || "";
        ajusterZoneTexte();
        form.requestSubmit();
    });
});

themeToggle.addEventListener("click", () => {
    const sombre = document.documentElement.dataset.theme === "dark";

    if (sombre) {
        document.documentElement.removeAttribute("data-theme");
    } else {
        document.documentElement.dataset.theme = "dark";
    }

    try {
        localStorage.setItem("theme", sombre ? "light" : "dark");
    } catch (error) {
        /* Le changement reste valable pour la page courante. */
    }

    actualiserBoutonTheme();
});

document.querySelectorAll("[data-product-dialog-close]").forEach((button) => {
    button.addEventListener("click", () => productDialog.close());
});

productDialog.addEventListener("click", (event) => {
    if (event.target === productDialog) {
        productDialog.close();
    }
});

productDialog.addEventListener("close", () => {
    productDialogRequest += 1;
});

window.addEventListener("online", connecterTempsReel);
window.addEventListener("offline", () => {
    if (reconnexion) {
        clearTimeout(reconnexion);
        reconnexion = null;
    }
    if (socket) {
        socket.close();
    }
    reglerEtatConnexion("offline", "Hors connexion");
});

actualiserBoutonTheme();
ajusterZoneTexte();
connecterTempsReel();

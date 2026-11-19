// =====================================================================
//  TALLY XIII — programme des boîtiers Wi-Fi (ESP32)
//  • M5Stack ATOM Matrix (25 LED) / ATOM Lite (1 LED) : LED RGB sur GPIO 27, bouton sur GPIO 39
//  • boîtier ESP32 maison : ruban / anneau WS2812 sur GPIO 27, ou deux LED simples (rouge GPIO 25, verte GPIO 26)
//  Le boîtier rejoint le Wi-Fi de la régie et interroge Tally XIII (http://IP:8790/api/cam/N) toutes les 80 ms :
//  rouge = à l'antenne, vert = preview, numéro de caméra en blanc au repos.
//  Configuration par le câble USB depuis Tally XIII (« Programmer un boîtier ») : une ligne JSON
//    {"ssid":"…","mdp":"…","serveur":"192.168.1.20:8790","cam":3,"lum":40}
//  Bouton : appui court = caméra suivante (1 → 20), appui long = luminosité. À partir de 10, le numéro défile.
//  Application développée par Matthieu Lamotte — SUITE XIII / OS XIII.
// =====================================================================
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <Adafruit_NeoPixel.h>
#include <ArduinoJson.h>

#define VERSION "1.0"
#define PIN_PIX 27
#define NB_PIX 25
#define PIN_ROUGE 25
#define PIN_VERT 26
#define PIN_BOUTON 39

Preferences prefs;
Adafruit_NeoPixel pix(NB_PIX, PIN_PIX, NEO_GRB + NEO_KHZ800);
String ssid, mdp, serveur;
int cam = 1, lum = 40;
String etat = "inconnu", affiche = "";
unsigned long tReq = 0, tOk = 0, tBouton = 0;
int echecs = 0;
bool bas = false;
HTTPClient http;
WiFiClient client;

// chiffres 0–9 en 5×5 (une ligne = 5 bits, poids fort à gauche)
const uint8_t CHIFFRES[10][5] = {
  {0b01110, 0b01010, 0b01010, 0b01010, 0b01110}, {0b00100, 0b01100, 0b00100, 0b00100, 0b01110},
  {0b01110, 0b00010, 0b01110, 0b01000, 0b01110}, {0b01110, 0b00010, 0b00110, 0b00010, 0b01110},
  {0b01010, 0b01010, 0b01110, 0b00010, 0b00010}, {0b01110, 0b01000, 0b01110, 0b00010, 0b01110},
  {0b01110, 0b01000, 0b01110, 0b01010, 0b01110}, {0b01110, 0b00010, 0b00100, 0b00100, 0b00100},
  {0b01110, 0b01010, 0b01110, 0b01010, 0b01110}, {0b01110, 0b01010, 0b01110, 0b00010, 0b01110}};

uint8_t l(int v) { return (uint8_t)(v * lum / 100); }

void tout(uint8_t r, uint8_t g, uint8_t b) {
  for (int i = 0; i < NB_PIX; i++) pix.setPixelColor(i, pix.Color(r, g, b));
  pix.show();
}

int defil = 0;  // décalage du défilement pour les numéros à deux chiffres

// colonne x (0 = gauche) du numéro n écrit en chiffres de 3 colonnes séparés d'une colonne vide, suivi d'un espace
uint8_t colonne(int n, int x) {
  char s[4]; snprintf(s, sizeof s, "%d", n);
  int L = strlen(s), total = L * 4 + 2;
  x = ((x % total) + total) % total;
  int d = x / 4, cx = x % 4;
  if (d >= L || cx == 3) return 0;
  uint8_t col = 0;
  for (int y = 0; y < 5; y++) if (CHIFFRES[s[d] - '0'][y] & (1 << (3 - cx))) col |= 1 << y;
  return col;
}

void chiffre(int n, uint8_t r, uint8_t g, uint8_t b) {
  pix.clear();
  if (n < 10) {
    const uint8_t *c = CHIFFRES[n % 10];
    for (int y = 0; y < 5; y++)
      for (int x = 0; x < 5; x++)
        if (c[y] & (1 << (4 - x))) pix.setPixelColor(y * 5 + x, pix.Color(r, g, b));
  } else {  // 10 à 40 : le numéro défile de droite à gauche
    for (int x = 0; x < 5; x++) {
      uint8_t col = colonne(n, x + defil);
      for (int y = 0; y < 5; y++) if (col & (1 << y)) pix.setPixelColor(y * 5 + x, pix.Color(r, g, b));
    }
  }
  pix.setPixelColor(0, pix.Color(r, g, b));  // ATOM Lite : sa seule LED reste allumée
  pix.show();
}

void dessiner(const String &e) {
  digitalWrite(PIN_ROUGE, e == "programme");
  digitalWrite(PIN_VERT, e == "preview");
  if (e == "programme") tout(l(255), 0, 0);
  else if (e == "preview") tout(0, l(200), 0);
  else if (e == "repos") chiffre(cam, l(60), l(60), l(60));
  else if (e == "wifi") chiffre(cam, l(255), l(120), 0);      // orange : pas de Wi-Fi
  else if (e == "serveur") chiffre(cam, 0, l(80), l(255));    // bleu : Tally XIII injoignable
  else chiffre(cam, l(80), 0, l(160));                       // violet : non configuré
}

void charger() {
  prefs.begin("tally", true);
  ssid = prefs.getString("ssid", ""); mdp = prefs.getString("mdp", ""); serveur = prefs.getString("serveur", "");
  cam = prefs.getInt("cam", 1); lum = prefs.getInt("lum", 40);
  prefs.end();
}

void sauver() {
  prefs.begin("tally", false);
  prefs.putString("ssid", ssid); prefs.putString("mdp", mdp); prefs.putString("serveur", serveur);
  prefs.putInt("cam", cam); prefs.putInt("lum", lum);
  prefs.end();
}

void identite() {
  Serial.printf("{\"app\":\"XIII-TALLY\",\"version\":\"%s\",\"ssid\":\"%s\",\"serveur\":\"%s\",\"cam\":%d,\"lum\":%d,\"wifi\":%s,\"ip\":\"%s\",\"etat\":\"%s\"}\n",
                VERSION, ssid.c_str(), serveur.c_str(), cam, lum, WiFi.status() == WL_CONNECTED ? "true" : "false",
                WiFi.localIP().toString().c_str(), etat.c_str());
}

void connecterWifi() {
  if (ssid.length() == 0) return;
  WiFi.mode(WIFI_STA); WiFi.setSleep(false); WiFi.setAutoReconnect(true);
  WiFi.begin(ssid.c_str(), mdp.c_str());
}

void lireSerie() {
  if (!Serial.available()) return;
  String ligne = Serial.readStringUntil('\n'); ligne.trim();
  if (ligne == "?" || ligne == "") { identite(); return; }
  JsonDocument d;
  if (deserializeJson(d, ligne)) { Serial.println("{\"erreur\":\"json\"}"); return; }
  bool wifi = false;
  if (d["ssid"].is<const char *>()) { ssid = (const char *)d["ssid"]; wifi = true; }
  if (d["mdp"].is<const char *>()) { mdp = (const char *)d["mdp"]; wifi = true; }
  if (d["serveur"].is<const char *>()) serveur = (const char *)d["serveur"];
  if (d["cam"].is<int>()) cam = constrain((int)d["cam"], 1, 40);
  if (d["lum"].is<int>()) lum = constrain((int)d["lum"], 5, 100);
  sauver();
  if (wifi) { WiFi.disconnect(); connecterWifi(); }
  affiche = ""; identite();
}

void bouton() {
  bool b = digitalRead(PIN_BOUTON) == LOW;
  if (b && !bas) { bas = true; tBouton = millis(); }
  if (!b && bas) {
    bas = false;
    if (millis() - tBouton > 700) lum = lum >= 100 ? 10 : lum + 30;
    else cam = cam >= 20 ? 1 : cam + 1;
    sauver(); affiche = ""; dessiner("repos"); delay(600);
  }
}

void setup() {
  Serial.begin(115200); Serial.setTimeout(200);
  pinMode(PIN_ROUGE, OUTPUT); pinMode(PIN_VERT, OUTPUT); pinMode(PIN_BOUTON, INPUT);
  pix.begin(); charger();
  dessiner(ssid.length() ? "wifi" : "config");
  connecterWifi();
  identite();
}

void loop() {
  lireSerie();
  bouton();
  String e;
  if (ssid.length() == 0 || serveur.length() == 0) e = "config";
  else if (WiFi.status() != WL_CONNECTED) e = "wifi";
  else if (millis() - tReq >= 80) {
    tReq = millis();
    http.setReuse(true); http.setTimeout(400);
    if (http.begin(client, "http://" + serveur + "/api/cam/" + String(cam))) {
      int code = http.GET();
      if (code == 200) { etat = http.getString(); etat.trim(); echecs = 0; tOk = millis(); }
      else echecs++;
      http.end();
    } else echecs++;
    e = echecs >= 6 ? "serveur" : etat;
  } else e = echecs >= 6 ? "serveur" : etat;
  static unsigned long tDefil = 0;
  if (cam >= 10 && e != "programme" && e != "preview" && millis() - tDefil > 170) { tDefil = millis(); defil++; affiche = ""; }
  if (e != affiche) { affiche = e; dessiner(e); }
  delay(5);
}

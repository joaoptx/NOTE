#include <Arduino.h>
#include "heltec.h"
#include <SPI.h>
#include <RadioLib.h>

// -------------------------
// Pinout LoRa Heltec WiFi LoRa 32 V3 (ESP32-S3 + SX1262)
// -------------------------
#define LORA_SCK   9
#define LORA_MISO  11
#define LORA_MOSI  10
#define LORA_CS    8
#define LORA_RST   12
#define LORA_BUSY  13
#define LORA_DIO1  14

// Configs LoRa para casar com o CubeCell
#define LORA_FREQUENCY         915.0    // MHz
#define LORA_BW_KHZ            125.0    // 0 => 125 kHz no CubeCell
#define LORA_SPREADING_FACTOR  7        // SF7
#define LORA_CODING_RATE       5        // 4/5 -> passar 5 pra RadioLib
#define LORA_PREAMBLE_LEN      8        // mesmo do CubeCell
#define LORA_SYNC_WORD         0x12     // <- CASANDO COM P2P "privado"

// SX1262 conectado ao ESP32-S3
SX1262 radio = new Module(LORA_CS, LORA_DIO1, LORA_RST, LORA_BUSY);

void setup() {
  Serial.begin(115200);
  delay(2000);

  // Display ON, LoRa interno OFF, Serial ON, PA ON
  Heltec.begin(true /*Display*/, false /*LoRa*/, true /*Serial*/, true /*PABOOST*/, 915E6);

  pinMode(LED, OUTPUT);
  digitalWrite(LED, LOW);

  // SPI nos pinos do rádio da Heltec V3
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_CS);

  Heltec.display->clear();
  Heltec.display->drawString(0, 0, "Init SX1262...");
  Heltec.display->display();

  // Inicializa SX1262 batendo com o CubeCell
  int state = radio.begin(
      LORA_FREQUENCY,        // MHz
      LORA_BW_KHZ,           // kHz
      LORA_SPREADING_FACTOR, // SF7
      LORA_CODING_RATE,      // 5 -> 4/5
      LORA_SYNC_WORD,        // 0x12 (P2P private)
      14,                    // dBm
      LORA_PREAMBLE_LEN      // 8 símbolos
      // tcxoVoltage fica 1.6 V por default (TCXO na Heltec V3)
  );

  if (state != RADIOLIB_ERR_NONE) {
    Serial.print("Falha ao iniciar SX1262, code ");
    Serial.println(state);

    Heltec.display->clear();
    Heltec.display->drawString(0, 0, "SX1262 FAIL");
    Heltec.display->drawString(0, 15, "Code: " + String(state));
    Heltec.display->display();

    while (true) {
      delay(1000);
    }
  }

  Serial.println("SX1262 OK, aguardando pacotes...");
  Heltec.display->clear();
  Heltec.display->drawString(0, 0, "LoRa RX OK");
  Heltec.display->drawString(0, 15, "Aguardando dados...");
  Heltec.display->display();
}

void loop() {
  String msg;

  // Recepção bloqueante - espera pacote
  int state = radio.receive(msg);

  if (state == RADIOLIB_ERR_NONE) {
    digitalWrite(LED, HIGH);

    Serial.print("Pacote recebido: ");
    Serial.println(msg);

    // Espera "temp,uv"
    float temp = NAN;
    int uv = 0;
    int commaIndex = msg.indexOf(',');

    if (commaIndex > 0) {
      temp = msg.substring(0, commaIndex).toFloat();
      uv = msg.substring(commaIndex + 1).toInt();
    }

    float rssi = radio.getRSSI();
    float snr  = radio.getSNR();

    Heltec.display->clear();
    Heltec.display->drawString(0, 0, "Pacote RX!");
    Heltec.display->drawString(0, 12, "Bruto: " + msg);

    if (!isnan(temp)) {
      Heltec.display->drawString(0, 24, "T: " + String(temp, 1) + " C");
      Heltec.display->drawString(0, 36, "UV: " + String(uv));
    }

    Heltec.display->drawString(0, 48,
      "RSSI:" + String(rssi, 1) + " SNR:" + String(snr, 1));
    Heltec.display->display();

    delay(80);
    digitalWrite(LED, LOW);
  }
  else if (state != RADIOLIB_ERR_RX_TIMEOUT) {
    // Se for timeout, ignora; se for outro erro, loga
    Serial.print("Erro RX: ");
    Serial.println(state);
  }

  // Loop volta a ouvir
}

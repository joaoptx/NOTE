#include <Arduino.h>
#include "heltec.h"
#include <SPI.h>
#include <RadioLib.h>

// -----------------------
// Pinos SX1262 na Heltec V3
// -----------------------
#define LORA_SCK   9
#define LORA_MISO  11
#define LORA_MOSI  10
#define LORA_CS    8
#define LORA_RST   12
#define LORA_BUSY  13
#define LORA_DIO1  14

SX1262 radio = new Module(LORA_CS, LORA_DIO1, LORA_RST, LORA_BUSY);

// -----------------------
// Parâmetros LoRa (batem com CubeCell RX)
// -----------------------
#define LORA_FREQUENCY     915.0    // MHz
#define LORA_BW_KHZ        125.0    // 0 => 125 kHz
#define LORA_SPREAD_FACTOR 7        // SF7
#define LORA_CODING_RATE   5        // 4/5
#define LORA_PREAMBLE_LEN  8
#define LORA_SYNC_WORD     0x12     // private sync word (igual CubeCell)

// -----------------------
// Pinos dos sensores (ajuste se necessário)
// -----------------------
#define PIN_LM35   3   // A3 da Heltec V3
#define PIN_UV     2   // A1 da Heltec V3

// -----------------------
// Funções de leitura dos sensores
// -----------------------
float lerLM35() {
  int raw = analogRead(PIN_LM35);           // 0..4095
  float v = raw * (3.3 / 4095.0);         // 3.3 V ref
  float tempC = v / 0.01;                  // 10 mV/°C
  return tempC;
}

int lerUV() {
  int raw = analogRead(PIN_UV);
  float v = (raw / 4095.0f) * 3.3f;
  int mV = (int)(v * 1000.0f + 0.5f);

  // Mesma lógica que você já usava
  if (mV < 50) return 0;
  else if (mV < 227) return 1;
  else if (mV < 318) return 2;
  else if (mV < 408) return 3;
  else if (mV < 503) return 4;
  else if (mV < 606) return 5;
  else if (mV < 696) return 6;
  else if (mV < 795) return 7;
  else if (mV < 881) return 8;
  else if (mV < 976) return 9;
  else if (mV < 1079) return 10;
  else return 11;
}

void setup() {
  Serial.begin(115200);
  delay(2000);

  // Display ON, LoRa interno OFF (vamos usar RadioLib), Serial ON, PA ON
  Heltec.begin(true /*Display*/, false /*LoRa*/, true /*Serial*/, true /*PABOOST*/, 915E6);
  pinMode(LED, OUTPUT);
  digitalWrite(LED, LOW);

  // ADC
  analogReadResolution(12);   // 0..4095

  // SPI para o SX1262
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_CS);

  Heltec.display->clear();
  Heltec.display->drawString(0, 0, "Heltec TX LoRa");
  Heltec.display->drawString(0, 12, "Init SX1262...");
  Heltec.display->display();

  // Inicializa rádio batendo com o CubeCell
  int state = radio.begin(
      LORA_FREQUENCY,
      LORA_BW_KHZ,
      LORA_SPREAD_FACTOR,
      LORA_CODING_RATE,
      LORA_SYNC_WORD,
      14,                  // dBm
      LORA_PREAMBLE_LEN    // 8 símbolos
      // tcxoVoltage default = 1.6 V (TCXO na Heltec V3)
  );

  if (state != RADIOLIB_ERR_NONE) {
    Serial.print("Falha SX1262, code ");
    Serial.println(state);

    Heltec.display->clear();
    Heltec.display->drawString(0, 0, "SX1262 FAIL");
    Heltec.display->drawString(0, 12, "Code: " + String(state));
    Heltec.display->display();
    while (true) {
      delay(1000);
    }
  }

  Serial.println("SX1262 OK, pronto p/ TX");

  Heltec.display->clear();
  Heltec.display->drawString(0, 0, "LoRa TX OK");
  Heltec.display->drawString(0, 12, "Enviando dados...");
  Heltec.display->display();
}

void loop() {
  // Le sensores
  float temp = lerLM35();
  int uv = lerUV();

  // Monta payload "temp,uv"
  String payload = String(temp, 1) + "," + String(uv);

  Serial.print("Enviando: ");
  Serial.println(payload);

  // Atualiza display
  Heltec.display->clear();
  Heltec.display->drawString(0, 0, "LoRa TX");
  Heltec.display->drawString(0, 12, "T: " + String(temp, 1) + " C");
  Heltec.display->drawString(0, 24, "UV: " + String(uv));
  Heltec.display->drawString(0, 40, "Pkt: " + payload);
  Heltec.display->display();

  digitalWrite(LED, HIGH);
  int state = radio.transmit(payload.c_str());
  digitalWrite(LED, LOW);

  if (state == RADIOLIB_ERR_NONE) {
    Serial.println("TX OK");
  } else {
    Serial.print("Falha TX, code ");
    Serial.println(state);
  }

  // Envia a cada 5 s (ajuste se quiser)
  delay(5000);
}

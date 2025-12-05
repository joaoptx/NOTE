#include "LoRaWan_APP.h"
#include <Arduino.h>

// -----------------------
// Config LoRa (casando com a Heltec TX)
// -----------------------
#define RF_FREQUENCY          915000000  // Hz
#define LORA_BANDWIDTH        0          // 0: 125 kHz
#define LORA_SPREADING_FACTOR 7          // SF7
#define LORA_CODINGRATE       1          // 1: 4/5
#define LORA_PREAMBLE_LENGTH  8          // símbolos
#define LORA_SYMBOL_TIMEOUT   0
#define LORA_FIX_LENGTH_PAYLOAD_ON false
#define LORA_IQ_INVERSION_ON  false

#define RX_TIMEOUT_VALUE      1000
#define BUFFER_SIZE           64

char rxpacket[BUFFER_SIZE];
static RadioEvents_t RadioEvents;

bool lora_idle = true;

void OnRxDone(uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr);

void setup() {
  boardInitMcu();
  Serial.begin(115200);

  Serial.println("CubeCell LoRa RX iniciado...");

  // Configura callbacks
  RadioEvents.RxDone = OnRxDone;
  Radio.Init(&RadioEvents);
  Radio.SetChannel(RF_FREQUENCY);

  Radio.SetRxConfig(
      MODEM_LORA,
      LORA_BANDWIDTH,
      LORA_SPREADING_FACTOR,
      LORA_CODINGRATE,
      0,                      // fixed: não usamos freq offset
      LORA_PREAMBLE_LENGTH,
      LORA_SYMBOL_TIMEOUT,
      LORA_FIX_LENGTH_PAYLOAD_ON,
      0,                      // payloadLen (0 = variável)
      true,                   // CRC on
      0,
      0,
      LORA_IQ_INVERSION_ON,
      true                    // rxContinuous
  );

  lora_idle = true;
}

void loop() {
  if (lora_idle) {
    lora_idle = false;
    Serial.println("Entrando em modo RX...");
    Radio.Rx(0);    // 0 = sem timeout (usa RX contínuo)
  }

  // CubeCell trata IRQ internamente, não precisa de Radio.IrqProcess()
}

// Callback chamado quando chega um pacote
void OnRxDone(uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr) {
  if (size >= BUFFER_SIZE) size = BUFFER_SIZE - 1;

  memcpy(rxpacket, payload, size);
  rxpacket[size] = '\0';

  String msg = String(rxpacket);
  float temp = NAN;
  int uv = 0;

  int comma = msg.indexOf(',');
  if (comma > 0) {
    temp = msg.substring(0, comma).toFloat();
    uv   = msg.substring(comma + 1).toInt();
  }

  Serial.println("====== PACOTE RECEBIDO ======");
  Serial.print("Bruto: ");
  Serial.println(msg);
  Serial.print("RSSI: ");
  Serial.print(rssi);
  Serial.print(" dBm | SNR: ");
  Serial.println(snr);

  if (!isnan(temp)) {
    Serial.print("Temperatura: ");
    Serial.print(temp, 1);
    Serial.print(" C  |  UV: ");
    Serial.println(uv);
  } else {
    Serial.println("Formato inesperado (esperado: temp,uv)");
  }
  Serial.println("=============================");

  Radio.Sleep();
  lora_idle = true;
}

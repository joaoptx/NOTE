#include "LoRaWan_APP.h"
#include <Arduino.h>

// Configurações do LoRa
#define RF_FREQUENCY        915000000 // Hz 
#define TX_OUTPUT_POWER     14        // dBm
#define LORA_BANDWIDTH      0         // [0: 125 kHz, 1: 250 kHz, 2: 500 kHz]
#define LORA_SPREADING_FACTOR 7       // [SF7..SF12]
#define LORA_CODINGRATE     1         // [1: 4/5]
#define LORA_PREAMBLE_LENGTH 8        // Same for Tx and Rx
#define LORA_SYMBOL_TIMEOUT 0         // Symbols
#define LORA_FIX_LENGTH_PAYLOAD_ON false
#define LORA_IQ_INVERSION_ON false

// Pinout
#define PIN_LM35 ADC
#define PIN_UV   GPIO1 

// Variáveis globais LoRa
static RadioEvents_t RadioEvents;
void OnTxDone( void );
void OnTxTimeout( void );

void setup() {
    boardInitMcu(); // Inicialização específica do CubeCell
    Serial.begin(115200);

    // Inicialização LoRa P2P
    RadioEvents.TxDone = OnTxDone;
    RadioEvents.TxTimeout = OnTxTimeout;
    Radio.Init(&RadioEvents);
    Radio.SetChannel(RF_FREQUENCY);
    Radio.SetTxConfig(MODEM_LORA, TX_OUTPUT_POWER, 0, LORA_BANDWIDTH,
                      LORA_SPREADING_FACTOR, LORA_CODINGRATE,
                      LORA_PREAMBLE_LENGTH, LORA_FIX_LENGTH_PAYLOAD_ON,
                      true, 0, 0, LORA_IQ_INVERSION_ON, 3000);
    
    Serial.println("CubeCell LoRa Sender Iniciado...");
}

// Funções Auxiliares dos Sensores

float lerLM35() {

    uint16_t adc = analogRead(PIN_LM35);
    float tensao = adc * (3.3 / 4095.0);
    return tensao / 0.01; // 10mV/°C
}

int lerUV() {
    uint16_t adc = analogRead(PIN_UV);
    float tensao = adc * (3.3 / 4095.0);
    int mV = tensao * 1000;

    // Lógica do seu código original
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

void loop() {
    // Leitura
    float temp = lerLM35();
    int uv = lerUV();

    // Formatação do Pacote ("Temp,UV")
    String pacote = String(temp, 1) + "," + String(uv);
    
    // Debug Serial
    Serial.print("Enviando: ");
    Serial.println(pacote);

    // Envio LoRa
    // Precisamos converter String para array de bytes
    uint8_t buffer[50];
    pacote.getBytes(buffer, pacote.length() + 1);
    
    Radio.Send(buffer, pacote.length());

    // Espera e Low Power
    delay(5000); // Envia a cada 5 segundos
    
    // Processa interrupções de rádio
    Radio.IrqProcess();
}

// Callbacks do LoRa 
void OnTxDone( void ) {
    Serial.println("TX Completo!");
    Radio.Sleep();
}

void OnTxTimeout( void ) {
    Serial.println("TX Timeout...");
    Radio.Sleep();
}
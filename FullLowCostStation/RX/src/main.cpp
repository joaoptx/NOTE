#include "heltec.h"

// Configurações LoRa 
#define BAND    915E6  

void setup() {
  // Inicializa a placa Heltec (Display, LoRa, Serial, PAMP, BaudRate)
  Heltec.begin(true /*Display*/, true /*LoRa*/, true /*Serial*/, true /*PAMP*/, BAND);

  // Ajuste Fino para combinar com o CubeCell 
  LoRa.setSpreadingFactor(7);
  LoRa.setSignalBandwidth(125E3); 
  LoRa.setCodingRate4(5); // Coding Rate 1 no CubeCell equivale a 4/5

  Serial.println("Receptor LoRa Iniciado. A aguardar dados...");
  
  // Mensagem inicial no OLED
  Heltec.display->clear();
  Heltec.display->drawString(0, 0, "Gateway LoRa ON");
  Heltec.display->drawString(0, 10, "A aguardar...");
  Heltec.display->display();
}

void loop() {
  // Tenta analisar o pacote
  int packetSize = LoRa.parsePacket();
  
  if (packetSize) {
    // Pacote recebido!
    String dadosRecebidos = "";

    // Ler o pacote byte a byte
    while (LoRa.available()) {
      dadosRecebidos += (char)LoRa.read();
    }

    // Enviar para a Serial 
    // O formato será exatamente o que o CubeCell enviou: "25.5,3"
    Serial.println(dadosRecebidos);

    // Atualizar o Display OLED (Para depuração visual)
    Heltec.display->clear();
    Heltec.display->drawString(0, 0, "Pacote Recebido!");
    Heltec.display->drawString(0, 15, "Dados: " + dadosRecebidos);
    Heltec.display->drawString(0, 30, "RSSI: " + String(LoRa.packetRssi()));
    Heltec.display->display();
    
    // Pequeno piscar do LED da placa para indicar receção
    digitalWrite(LED, HIGH);
    delay(100);
    digitalWrite(LED, LOW);
  }
}
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import time
import socket
import mraa

# Configuration.

SENSOR_ADC_PIN = 0 # Used by the ADC (pin A0).
BUTTON_PULLUP_PIN = 4 # Used by the Hi-Z button.

LED_SENSOR_PWM_PIN = 5
LED_DRYER_PWM_PIN = 6 
LED_SYSTEM_PIN = 7 

MODE1_TIME = 180
MODE2_TIME = 60

LIGHT_THRESHOLD = 40 # Value from 0 to 100.
HIGH_LIGHT_WEIGHT = 0.5  # Value from 0 to 1.

SDC_IP = "10.9.99.167"
PORT = 18000
MESSAGE = "Oi, Denis"




# Handles button interruption on falling edge.   
def button_pressed(pin):
    time.sleep(0.1) # debounce delay
    if system.running:
        print '[button] The system has been stopped.' 
        system.stop()
        return
    print '[button] The system has been started.' 
    system.start()     
     
class ADCThread(threading.Thread):

    def __init__(self):
        super(ADCThread, self).__init__()
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()
        
    def run(self):    
        while True:
           if self.stopped():
                exit()  
           system.update_sensor_value()
           time.sleep(0.1)

''' 
Function that controls the PWM signal.
'''          
class PWMThread(threading.Thread):   
                         
    def __init__(self):
        super(PWMThread, self).__init__()
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()
        
    def run(self):   
        counter = 0 
        while True:
            if self.stopped():
                exit()
            
            # Changes the duty cycle of both PWM signals.
            system.set_sensor_pwm_duty()

            if counter > 9:
                system.set_dryer_pwm_duty()
                counter = 0
            
            counter += 1
            time.sleep(0.1) 
            
                  
''' 
Function that controls the curve signal.
'''          
class ControlThread(threading.Thread):   
                         
    def __init__(self):
        super(ControlThread, self).__init__()
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()
        
    def run(self):    
        current_time = 0
        while True:
            
           if self.stopped():
                exit()  
            
           system.calculate_pwm_dryer()
           system.advance_time()
           time.sleep(1)
           

class NetworkThread(threading.Thread):

    def __init__(self):
        super(NetworkThread, self).__init__()
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()
        
    def run(self):    
        while True:
           if self.stopped():
                exit()  
           
           system.send_info_to_sdc()
           time.sleep(1)  


class System:
          
    def update_sensor_value(self):
        self.sensor_value = int(100 * (self.adc.read() / 1024.0))

    def set_sensor_pwm_duty(self):
        self.led_sensor.write(self.sensor_value/100.0)
        #print '[pwm1] Sensor PWM (ADC relative value): %d %%' %self.sensor_value
        
    def set_dryer_pwm_duty(self):
        
        duty =  self.pwm_dryer
        
        # apply a weight based on sensor value.
        if self.sensor_value > LIGHT_THRESHOLD:
            duty *= HIGH_LIGHT_WEIGHT

        self.led_dryer.write(duty/100.0) 
        print '[pwm] Dryer PWM: %d %%' %(duty) 
        print '[adc] Sensor value: %d %%' %(self.sensor_value)
        
        
    def calculate_pwm_dryer(self):
       if self.mode == 1:
           self.pwm_dryer = system.dryer_mode1()
       elif self.mode == 2:
           self.pwm_dryer = system.dryer_mode2()

    def __init__(self):
    
        # Important variables.
        self.threads = {}
        self.running = False
        self.sensor_value = 0
        self.seconds = 0
        self.mode = 1
        self.pwm_dryer = 0
        
        # Configure the digital output for the LED 3.     
        self.led_system = mraa.Gpio(LED_SYSTEM_PIN) 
        self.led_system.dir(mraa.DIR_OUT)   

        # Configures the PWM generators (LEDs and dryer).
        self.led_sensor = mraa.Pwm(LED_SENSOR_PWM_PIN)
        self.led_sensor.period_ms(5)
         
        self.led_dryer = mraa.Pwm(LED_DRYER_PWM_PIN)
        self.led_dryer.period_ms(5)

        # Configures the Hi-Z button.
        self.button = mraa.Gpio(BUTTON_PULLUP_PIN) 
        self.button.dir(mraa.DIR_IN)        
        self.button.mode(mraa.MODE_PULLUP)
        self.button.isr(mraa.EDGE_FALLING, button_pressed, self.button)   

        # Configures the ADC.
        self.adc = mraa.Aio(SENSOR_ADC_PIN)
        
        # Configures the socket.
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
        
    def send_info_to_sdc(self):
        if self.running:
            status = '+'
        else:
            status = '-'
        info = "%d;%d;%d%s" %(self.seconds, self.sensor_value, 
            self.pwm_dryer, status)
            
        self.sock.sendto(info, (SDC_IP, PORT))
        
    def adc_start(self):
        # Start ADC thread.
        self.threads['adc'] = ADCThread()
        self.threads['adc'].setDaemon(True)
        self.threads['adc'].start()
        
    def adc_stop(self):
        self.threads['adc'].stop()
        
    def pwm_start(self): 
        self.led_sensor.enable(True)
        self.led_dryer.enable(True)
        self.led_dryer.write(0)
        
        # Start the PWM thread.
        self.threads['pwm'] = PWMThread()
        self.threads['pwm'].setDaemon(True)
        self.threads['pwm'].start()
        
    def pwm_stop(self):
        self.threads['pwm'].stop()
        self.led_sensor.enable(False)
        self.led_dryer.enable(False)
        
        
    def control_start(self):
        self.threads['control'] = ControlThread()
        self.threads['control'].setDaemon(True)
        self.threads['control'].start()
        
    def control_stop(self):
        self.threads['control'].stop()
        
   
    def network_start(self):
        self.threads['network'] = NetworkThread()
        self.threads['network'].setDaemon(True)
        self.threads['network'].start()
        
    def network_stop(self):
        self.threads['network'].stop()
   

    def start(self):
        self.running = True
        self.led_system.write(1)
        
        self.adc_start()
        self.pwm_start()
        self.control_start()
        self.network_start()

    def stop(self):
        self.running = False
        self.sensor_value = 0
        self.seconds = 0
        
        self.led_system.write(0)
        system.send_info_to_sdc()
        
        self.adc_stop()
        self.pwm_stop()
        self.control_stop()
        self.network_stop()
        

    def advance_time(self):
        self.seconds += 1
        if self.mode == 1:
            if self.seconds > MODE1_TIME:
                self.stop()
                print '[time] system has been stopped'
        elif self.mode == 2:
            if self.seconds > MODE2_TIME:
                self.stop()
                print '[time] system has been stopped'

    def dryer_mode1(self):
    
        if self.seconds <= 30:
            result = self.seconds
        elif self.seconds > 30 and self.seconds <= 60:
            result = 30
        elif self.seconds > 60 and self.seconds <= 90:
            result = int(1.5 * self.seconds - 60)
        elif self.seconds > 90 and self.seconds <= 120:
            result = 75
        elif self.seconds > 120 and self.seconds <= 180:
            result = int(-1.25 * self.seconds + 225)
        else:
            result = 0
        return result

    def dryer_mode2(self):
    
        if self.seconds <= 10:
            result = 10 * self.seconds
        elif self.seconds > 10 and self.seconds < 50:
            result = 100;
        else:
            result = int(-10 * self.seconds + 600)    
        return result


if __name__ == "__main__":
    system = System()
    while True: pass
 

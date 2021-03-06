/* OSU Robotics Club Rover 2016
 * Miniboard Firmware
 * 
 * miniboard.c - Main control loop.
 * Author(s): Nick Ames
 */
#include <avr/interrupt.h>
#define F_CPU 16000000UL
#include <util/delay.h>
#include <util/atomic.h>
#include "uart.h"
#include "comm.h"
#include "commgen.h"
#include "adc.h"
#include "sabertooth.h"
#include "callsign.h"
#include "gps.h"

#include <stdio.h>
#include <string.h>

/* TODO: Watchdog timer. */
/* TODO: Debug facilities. */
/* TODO: Fix unnecessary memory consumption of variable-length registers. */

/* Triggers for data read commands. */
void camera_command_trigger(void){
	
}

void debugging_info_trigger(void){
	
}

void callsign_trigger(void){
	
}

void build_info_trigger(void){

}


/* ISR that fires if an interrupt is enabled without a corresponding handler. */
ISR(BADISR_vect){
	DDRB |= _BV(PB7);
	while(1){
		PORTB |= _BV(PB7);
		_delay_ms(100);
		PORTB &= ~_BV(PB7);
		_delay_ms(200);
		PORTB |= _BV(PB7);
		_delay_ms(300);
		PORTB &= ~_BV(PB7);
		_delay_ms(300);
	}
}

/* Setup all peripherals and subsystems. */
void init(void){
	comm_init();
	gps_init();
	//sabertooth_init();
	//set_callsign("asdf");
	sei();
}

/* Get a value, then atomically set the target variable. */
#define atomic_set(target, value) do {typeof(target) __valstore = value; ATOMIC_BLOCK(ATOMIC_RESTORESTATE){target = __valstore;} } while(0)

void miniboard_main(void){
	init();
	/* Miniboard main loop. */
	while(1){
		/* (GPS handled in-module) */
		/* ADC (Pot channels and battery.) */
		atomic_set(Data->battery_voltage, battery_mV());
		atomic_set(Data->pot_1, pot_channel(1));
		atomic_set(Data->pot_2, pot_channel(2));
		atomic_set(Data->pot_3, pot_channel(3));
		atomic_set(Data->pot_4, pot_channel(4));
		atomic_set(Data->pot_5, pot_channel(5));
		
		DDRB |= _BV(PB7);
		PORTB ^= _BV(PB7);
		_delay_ms(300);
	}
}

int main(void){
	/* For testing, remove the following call and insert your code below.
	 * You might need to copy stuff from init(). Don't commit your modified
	 * miniboard.c to the main branch! */
	miniboard_main();
	return(0);
}

USE `futaba_ok2_iot`;
-- UPDATE `futaba_ok2_iot`.`t_input` SET `value`=0 WHERE `signal_id`=1600 AND `value`=1;
-- UPDATE `futaba_ok2_iot`.`t_input` SET `value`=0 WHERE `signal_id`=1601 AND `value`=1;
-- UPDATE `futaba_ok2_iot`.`t_output` SET `value`=0 WHERE  `signal_id`=1600 AND `value`=1;
-- UPDATE `futaba_ok2_iot`.`t_output` SET `value`=0 WHERE  `signal_id`=1601 AND `value`=1;

UPDATE `futaba_ok2_iot`.`t_input` SET `value`=0 WHERE `signal_id`=1800 AND `value`=1;
UPDATE `futaba_ok2_iot`.`t_input` SET `value`=0 WHERE `signal_id`=1801 AND `value`=1;
UPDATE `futaba_ok2_iot`.`t_output` SET `value`=0 WHERE  `signal_id`=1800 AND `value`=1;
UPDATE `futaba_ok2_iot`.`t_output` SET `value`=0 WHERE  `signal_id`=1801 AND `value`=1;


USE `futaba_ok2_shippment`;
UPDATE `futaba_ok2_shippment`.`t_line_status` SET `request_flag`=0, `permition`=0, `request_execution`=0 WHERE `line_id`=1; 
UPDATE `futaba_ok2_shippment`.`t_line_status` SET `request_flag`=0, `permition`=0, `request_execution`=0 WHERE `line_id`=2;
UPDATE `futaba_ok2_shippment`.`t_line_status` SET `request_flag`=0, `permition`=0, `request_execution`=0 WHERE `line_id`=3;
UPDATE `futaba_ok2_shippment`.`t_line_status` SET `request_flag`=0, `permition`=0, `request_execution`=0 WHERE `line_id`=4;

UPDATE `futaba_ok2_shippment`.`t_pallet_status` SET `status`="EMPTY" WHERE `status`="FILL";

UPDATE `futaba_ok2_shippment`.`t_kotatsu_status` SET `booking`=0 WHERE `booking`=1;

UPDATE `futaba_ok2_shippment`.`t_location` SET `transport_permission`=0, `has_reservation`=0 WHERE `transport_permission`=1 OR `has_reservation`=1;
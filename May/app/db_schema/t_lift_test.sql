UPDATE t_kotatsu_status SET loaded_pallet_id = NULL, booking = 0;

UPDATE t_location SET kotatsu_id = NULL, has_reservation = 0;

UPDATE t_lift_station SET pallet_id = NULL, transport_status = 'REDY'

SELECT pallet_id FROM t_pallet_status WHERE status = 'EMPTY';

UPDATE t_location SET kotatsu_id = 'OKE0003' WHERE cell_code = 27644368;  -- INPUT cell for T63

UPDATE t_kotatsu_status SET cell_code = 27644368 WHERE kotatsu_id = 'OKE0003';

UPDATE t_lift_station
SET pallet_id = 3, transport_status = 'WORK' WHERE plat_no = 81 AND seq_no = 0;

UPDATE t_line_status
SET request_flag = 1,
    request_execution = 0
WHERE line_id = 1;

SELECT kotatsu_id, loaded_pallet_id FROM t_kotatsu_status
WHERE kotatsu_id = 'OKE0003';

SELECT pallet_id, transport_status FROM t_lift_station;

SELECT * FROM t_location WHERE has_reservation = 1;

UPDATE t_pallet_status SET status = 'EMPTY' WHERE STATUS = "FILL";
UPDATE t_kotatsu_status SET loaded_pallet_id = NULL;
UPDATE t_lift_station SET transport_status = 'REDY'
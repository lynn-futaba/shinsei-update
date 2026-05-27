--
-- Table structure for table `m_error`
--
DROP TABLE IF EXISTS `m_error`;
CREATE TABLE `m_error` (
  `error_code` VARCHAR(50) NOT NULL COMMENT 'エラーコード、E1+6:RMS、E2+6：RMS通信異常,E3+6:WCSの運行中異常,E4+6：WCSの設定値異常',
  `error_category` VARCHAR(50) NOT NULL COMMENT 'エラー種別',
  `error_summary` VARCHAR(50) NOT NULL COMMENT 'エラー概要',
  `error_operation` VARCHAR(255) NOT NULL COMMENT 'エラー対応',
  `error_description` VARCHAR(255) NOT NULL COMMENT 'エラー詳細',
  `rms_error_code` BIT(50) NULL DEFAULT (0) COMMENT 'RMSエラーコード',
  `error_level` VARCHAR(10) NOT NULL COMMENT 'エラーレベル',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時(yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時(yyyy/MM/dd hh:mm:ss)',
  -- PRIMARY KEY (`error_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `m_kotatsu`
--
DROP TABLE IF EXISTS `m_kotatsu`;
CREATE TABLE `m_kotatsu` (
  `kotatsu_id` VARCHAR(8) NOT NULL COMMENT 'コタツID',
  `kotatsu_type` INT(5) NOT NULL COMMENT 'コタツ種類',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時',
  PRIMARY KEY (`kotatsu_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `m_lift_station`
--
DROP TABLE IF EXISTS `m_lift_station`;
CREATE TABLE `m_lift_station` (
	`plat_no` INT NOT NULL COMMENT 'plat番号',
	`seq_no` INT NOT NULL COMMENT 'seq番号',
	`maguchi_name` VARCHAR(20) NOT NULL DEFAULT '' COMMENT '間口１～７',
	`created_date` DATETIME NOT NULL DEFAULT (now()) COMMENT '作成日時(yyyy/MM/dd hh:mm:ss)',
	`updated_date` DATETIME NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時(yyyy/MM/dd hh:mm:ss)'
	) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE='utf8mb4_unicode_ci';

--
-- Table structure for table `m_line`
--
DROP TABLE IF EXISTS `m_line`;
CREATE TABLE `m_line` (
  `line_id` INT(15) NOT NULL COMMENT 'ラインID',
  `line_name` VARCHAR(18) NOT NULL COMMENT 'ライン名',
  `line_description` VARCHAR(50) NULL COMMENT 'ライン説明',
  `carry_pattern` INT NOT NULL DEFAULT '1' COMMENT '搬送パターン',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時(yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時(yyyy/MM/dd hh:mm:ss)',
  -- PRIMARY KEY (`line_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `m_location`
--
DROP TABLE IF EXISTS `m_location`;
CREATE TABLE `m_location` (
  `cell_code` INT(8) NOT NULL COMMENT 'セルコード',
  `cell_type` VARCHAR(20) NOT NULL COMMENT 'セルタイプ',
  `cell_name` VARCHAR(50) NOT NULL COMMENT 'セル名称',
  `cell_description` VARCHAR(50) NULL COMMENT 'セル説明',
  `plat_no` INT(2) NOT NULL COMMENT 'plat番号',
  `seq_no` INT(1) NOT NULL COMMENT 'seq番号',
  `angle` INT NOT NULL DEFAULT '0',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時(yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時(yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`cell_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `m_pallet`
--

DROP TABLE IF EXISTS `m_pallet`;
CREATE TABLE `m_pallet` (
  `pallet_type` INT(4) NOT NULL COMMENT 'パレット種類',
  `pallet_name` VARCHAR(50) NOT NULL COMMENT 'パレット名称',
  `versatility` TINYINT(1) NOT NULL COMMENT '汎用性 (0 = 専用, 1 = 汎用)',
  `line_id` INT NOT NULL COMMENT 'ラインID',
  `kotatsu_type` INT(5) NOT NULL COMMENT 'コタツ種類',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時(yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時(yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`pallet_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `m_product`
--
DROP TABLE IF EXISTS `m_product`;
CREATE TABLE `m_product` (
  `product_no` INT(15) NOT NULL COMMENT '製品番号',
  `product_name` VARCHAR(50) NOT NULL COMMENT '製品名称',
  `pallet_type` INT(15) NOT NULL COMMENT '使用パレット種類',
  `capacity` INT(4) NOT NULL COMMENT '収容数',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時(yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時(yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`product_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `m_robot`
--
DROP TABLE IF EXISTS `m_robot`;
CREATE TABLE `m_robot` (
  `robot_id` INT(8) NOT NULL COMMENT 'ロボットID',
  `robot_name` VARCHAR(10) NOT NULL COMMENT 'ロボット名称',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時(yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時(yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`robot_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `m_signal_list`
--
DROP TABLE IF EXISTS `m_signal_list`;
CREATE TABLE `m_signal_list` (
  `signal_id` INT(8) NOT NULL COMMENT '信号ID',
  `input_output_value` VARCHAR(8) NOT NULL COMMENT '入出力設定',
  `plat_no` INT(2) NOT NULL COMMENT 'plat番号',
  `seq_no` INT(1) NOT NULL COMMENT 'seq番号',
  `signal_type` VARCHAR(12) NOT NULL COMMENT '信号種類',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時 (yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時 (yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`error_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `m_station`
--
DROP TABLE IF EXISTS `m_station`;
CREATE TABLE `m_station` (
	`id` INT NOT NULL COMMENT 'ラインID',
	`name` VARCHAR(50) NOT NULL DEFAULT '""' COMMENT '間口パレット',
	`cell_type` VARCHAR(50) NOT NULL DEFAULT '""' COMMENT 'セルタイプ',
	`created_date` DATETIME NOT NULL DEFAULT (now()) COMMENT '作成日時(yyyy/MM/dd hh:mm:ss)',
	`updated_date` DATETIME NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP COMMENT '変更日時(yyyy/MM/dd hh:mm:ss)'
)  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `m_system_interlock`
--
DROP TABLE IF EXISTS `m_system_interlock`;
CREATE TABLE `m_system_interlock` (
  `system_id` VARCHAR(12) NOT NULL COMMENT 'システムID',
  `line_id` INT(15) NOT NULL COMMENT 'ラインID',
  `transport_permission` TINYINT(1) NOT NULL COMMENT '搬送許可 (1 = 許可, 0 = 禁止)',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時(yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時(yyyy/MM/dd hh:mm:ss)',
  -- PRIMARY KEY (`system_id`, `line_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `m_system_status`
--
DROP TABLE IF EXISTS `m_system_status`;
CREATE TABLE `m_system_status` (
  `system_id` VARCHAR(12) NOT NULL COMMENT 'システムID',
  `system_name` VARCHAR(50) NOT NULL COMMENT 'システム名称',
  `mode` TINYINT(1) NOT NULL COMMENT 'モード (1 = 自動, 0 = 各個)',
  `preparation_ok` TINYINT(1) NOT NULL COMMENT '運転準備 (1 = 完了, 0 = 未完)',
  `auto_running` TINYINT(1) NOT NULL COMMENT '自動運転 (1 = 運転中, 0 = 停止中)',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時(yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時(yyyy/MM/dd hh:mm:ss)',
  -- PRIMARY KEY (`system_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table: t_callback_task_events  (JSON version)
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `t_callback_task_events`;
CREATE TABLE `t_callback_task_events` (
	`task_id` VARCHAR(64) NOT NULL COMMENT 'タスクID',
	`request_id` VARCHAR(128) NOT NULL COMMENT 'Request ID',
	`event_json` JSON NOT NULL COMMENT '受信したフルJSON',
	`created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時(yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時(yyyy/MM/dd hh:mm:ss)',
	PRIMARY KEY (`task_id`, `request_id`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE='utf8mb4_unicode_ci';

-- ------------------------------------------------------------
-- Table: t_callback_task_status
-- ------------------------------------------------------------
DROP TABLE IF EXISTS `t_callback_task_status`;
CREATE TABLE `t_callback_task_status` (
	`task_id` VARCHAR(64) NOT NULL COMMENT 'タスクID',
	`status` VARCHAR(32) NOT NULL COMMENT 'Status',
	`phase` VARCHAR(64) NULL DEFAULT NULL COMMENT 'Phase',
	`robot_id` VARCHAR(64) NULL DEFAULT NULL COMMENT 'Robot ID',
	`dest_cell` VARCHAR(64) NULL DEFAULT NULL COMMENT 'Dest Cell',
	`task_type` VARCHAR(64) NULL DEFAULT NULL COMMENT 'Task Type',
	`instruction` VARCHAR(64) NULL DEFAULT NULL COMMENT 'Instruction',
	`created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時(yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時(yyyy/MM/dd hh:mm:ss)',
	PRIMARY KEY (`task_id`) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE='utf8mb4_unicode_ci';

--
-- Table structure for table `t_error_log`
--
DROP TABLE IF EXISTS `t_error_log`;
CREATE TABLE `t_error_log` (
  `error_num` INT(15) NOT NULL COMMENT 'エラーID',
  `error_code` VARCHAR(50) NOT NULL COMMENT 'エラーコード',
  `task_id` INT(12) NULL DEFAULT NULL COMMENT 'タスクID',
  `robot_id` INT(8) NULL DEFAULT NULL COMMENT 'ロボットID',
  `error_datetime` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'エラー発生時刻 (yyyy/MM/dd hh:mm:ss)',
  `is_completed` BIT(1) NOT NULL COMMENT '完了状況',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時 (yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時 (yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`error_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `t_kotatsu_status`
--
DROP TABLE IF EXISTS `t_kotatsu_status`;
CREATE TABLE `t_kotatsu_status` (
  `kotatsu_id` INT(8) NOT NULL COMMENT 'コタツID',
  `loaded_pallet_id` INT(8) NULL COMMENT '積載パレットID',
  `cell_code` INT NULL DEFAULT NULL COMMENT '現在位置',
	`booking` TINYINT(1) NOT NULL DEFAULT '0' COMMENT '予約(0:無し、1:有り)',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時 (yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時 (yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`kotatsu_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `t_lift_station`
--
DROP TABLE IF EXISTS `t_lift_station`;
CREATE TABLE `t_lift_station` (
  `plat_no` INT(2) NOT NULL COMMENT 'plat番号',
  `seq_no` INT(8) NULL COMMENT 'seq番号',
  `pallet_id` INT(15) NOT NULL COMMENT 'パレット名称',
  `transport_status` VARCHAR(8) NOT NULL COMMENT '搬送ステータス (READY, WORK, WAIT, COMP)',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時 (yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時 (yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`plat_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `t_line_station`
--
DROP TABLE IF EXISTS `t_line_station`;
CREATE TABLE `t_line_station` (
  `plat_no` INT(2) NOT NULL COMMENT 'plat番号',
  `line_id` INT(15) NOT NULL COMMENT 'ラインID',
  `pallet_id` INT(15) NOT NULL COMMENT 'パレット名称',
  `status` VARCHAR(8) NOT NULL COMMENT 'ステータス',
  `distination_plat` INT UNSIGNED NOT NULL COMMENT '排出プラット',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時 (yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時 (yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`plat_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `t_line_status`
--
DROP TABLE IF EXISTS `t_line_status`;
CREATE TABLE `t_line_status` (
  `line_id` INT(15) NOT NULL COMMENT 'ラインID',
  `request_flag` TINYINT(1) NOT NULL COMMENT '搬出要求flag (1 = 要求, 0 = なし)',
  `request_time` DATETIME NULL COMMENT '要求時間 (yyyy/MM/dd hh:mm:ss)',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時 (yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時 (yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`line_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `t_location`
--
DROP TABLE IF EXISTS `t_location`;
CREATE TABLE `t_location` (
  `cell_code` INT NULL DEFAULT NULL COMMENT 'セルコード',
  `kotatsu_id` INT(8) NOT NULL COMMENT 'コタツID',
  `transport_permission` TINYINT(1) NOT NULL COMMENT '搬送許可 (0 = 許可, 1 = 禁止)',
  `has_reservation` TINYINT(1) NOT NULL COMMENT '予約有無 (0 = 無し, 1 = 有)',
  `transport_status` VARCHAR(8) NOT NULL COMMENT '搬送ステータス (READY, WORK, WAIT, COMP)',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時 (yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時 (yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`line_id`, `kotatsu_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `t_pallet_status`
--
DROP TABLE IF EXISTS `t_pallet_status`;
CREATE TABLE `t_pallet_status` (
  `pallet_id` INT(8) NOT NULL COMMENT 'パレットID',
  `pallet_type` INT(4) NOT NULL COMMENT 'パレット種類',
  `status` VARCHAR(12) NOT NULL COMMENT 'ステータス ("FILL", "EMPTY")',
  `input_time` DATETIME NULL COMMENT '投入時間 (yyyy/MM/dd hh:mm:ss)',
  `completion_time` DATETIME NULL COMMENT '完成時間 (yyyy/MM/dd hh:mm:ss)',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時 (yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時 (yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`pallet_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `t_pallet_supply_pairs`
--
DROP TABLE IF EXISTS `t_pallet_supply_pairs`;
CREATE TABLE `t_pallet_supply_pairs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `line_id` INT NOT NULL,
    `pair_index` INT NOT NULL, 
    `pallet_type` INT DEFAULT NULL, -- Changed from pallet_name (varchar) to pallet_type (int)
    `count` INT NOT NULL DEFAULT 0,
    `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時 (yyyy/MM/dd hh:mm:ss)',
    INDEX `idx_line_pair` (`line_id`, `pair_index`) 
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP TABLE IF EXISTS `m_pallet_supply_pairs`;
CREATE TABLE `m_pallet_supply_pairs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `pattern_no` INT NOT NULL COMMENT 'Pattern number (1,2,3...)',
    `line_id` INT NOT NULL,
    `pair_index` INT NOT NULL,
    `pallet_type` INT NOT NULL,
    `count` INT NOT NULL DEFAULT 1,

    `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY `uk_pattern_line_pair`
        (`pattern_no`, `line_id`, `pair_index`),

    INDEX `idx_pattern` (`pattern_no`)
) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_unicode_ci;

INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (1, 1, 1, 0, 21, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (2, 1, 1, 1, 22, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (3, 1, 1, 2, 23, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (4, 1, 1, 3, 24, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (5, 1, 2, 0, 31, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (6, 1, 2, 1, 32, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (7, 1, 2, 2, 33, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (8, 1, 2, 3, 34, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (9, 1, 3, 0, 1, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (10, 1, 3, 1, 2, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (11, 1, 3, 2, 3, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (12, 1, 3, 3, 4, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (13, 1, 4, 0, 11, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (14, 1, 4, 1, 12, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (15, 1, 4, 2, 13, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (16, 1, 4, 3, 14, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (49, 2, 1, 0, 21, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (50, 2, 1, 1, 22, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (51, 2, 1, 2, 23, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (52, 2, 1, 3, 24, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (53, 2, 2, 0, 31, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (54, 2, 2, 1, 32, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (55, 2, 2, 2, 33, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (56, 2, 2, 3, 34, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (57, 2, 3, 0, 1, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (58, 2, 3, 1, 2, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (59, 2, 3, 2, 3, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (60, 2, 3, 3, 4, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (61, 2, 4, 0, 11, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (62, 2, 4, 1, 12, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (63, 2, 4, 2, 13, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (64, 2, 4, 3, 14, 1, '2026-05-01 16:38:52', '2026-05-01 16:38:52');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (65, 1, 3, 4, 0, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (66, 1, 4, 4, 10, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (67, 1, 1, 4, 20, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (68, 1, 2, 4, 30, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (69, 2, 3, 4, 0, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (70, 2, 4, 4, 10, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (71, 2, 1, 4, 20, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');
INSERT INTO `m_pallet_supply_pairs` (`id`, `pattern_no`, `line_id`, `pair_index`, `pallet_type`, `count`, `created_date`, `updated_date`) VALUES (72, 2, 2, 4, 30, 1, '2026-05-01 16:38:04', '2026-05-01 16:38:04');


--
-- Table structure for table `t_pallet_supply_status`
--
-- DROP TABLE IF EXISTS `t_pallet_supply_status`;
-- CREATE TABLE `t_pallet_supply_status` (
--     `line_id` INT(15) PRIMARY KEY,
--     `rev` INT NOT NULL DEFAULT 0,
--     `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時 (yyyy/MM/dd hh:mm:ss)'
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `t_product`
--
DROP TABLE IF EXISTS `t_product`;
CREATE TABLE `t_product` (
  `line_id` INT(15) NOT NULL COMMENT 'ラインID',
  `plan_no` INT(2) NOT NULL COMMENT '計画番号',
  `supply_pallet_type` INT(4) NOT NULL COMMENT '供給パレット種類',
  `planned_supply_qty` INT(4) NOT NULL COMMENT '供給予定数',
  `completed_supply_qty` INT(4) NOT NULL COMMENT '供給完了数',
  `updated_time` DATETIME NOT NULL COMMENT '更新時間 (yyyy/MM/dd hh:mm:ss)',
  `created_time` DATETIME NOT NULL COMMENT '生成時間 (yyyy/MM/dd hh:mm:ss)',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時 (yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時 (yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`line_id`, `plan_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `t_rms_error`
--
DROP TABLE IF EXISTS `t_rms_error`;
CREATE TABLE `t_rms_error` (
  `id` INT(11) NOT NULL AUTO_INCREMENT COMMENT 'Local Unique ID',
  `athena_id` INT(11) UNIQUE NOT NULL COMMENT 'Original ID from Athena t_monitor_exception_capture',
  `system_code` INT(11) NOT NULL COMMENT 'Error Number (e.g., 13001). Links to m_error.rms_error_code',
  `fault_status` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '0:Active, 1:Resolved',
  `occurrence_time` DATETIME NOT NULL COMMENT 'Taken from Athena create_time',
  `device_id` VARCHAR(50) DEFAULT NULL COMMENT 'Taken from Athena ext3 (Robot/Equipment ID)',
  `cell_code` VARCHAR(50) DEFAULT NULL COMMENT 'Storage/Location code from Athena',
  `is_completed` TINYINT NULL DEFAULT '0' COMMENT '0:Enabled, 1:Disabled',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時 (yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時 (yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`id`),
  INDEX `idx_system_code` (`system_code`),
  INDEX `idx_occurrence` (`occurrence_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `t_robot`
--
DROP TABLE IF EXISTS `t_robot`;
CREATE TABLE `t_robot` (
  `id` INT(8) NOT NULL COMMENT 'ロボトID',
  `task_id` INT(12) NULL COMMENT 'タスクID',
  `current_cell_position` INT(8) NOT NULL COMMENT '現在セル位置',
  `operation_status` VARCHAR(10) NOT NULL COMMENT '稼働状態',
  `loaded_kotatsu_id` INT(8) NULL COMMENT '積載コタツID',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時 (yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時 (yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `t_task`
--
DROP TABLE IF EXISTS `t_task`;
CREATE TABLE `t_task` (
  `task_id` INT UNSIGNED NOT NULL COMMENT 'タスクID',
	`robot_id` INT UNSIGNED NOT NULL COMMENT 'ロボットID',
	`status` VARCHAR(12) NOT NULL COMMENT 'ステータス(ACT, WORK, WAIT, COMP)',
	`start_cell` INT UNSIGNED NULL DEFAULT NULL COMMENT 'スタートセル',
	`end_cell` INT UNSIGNED NULL DEFAULT NULL COMMENT 'エンドセル',
	`priority` INT NULL DEFAULT NULL COMMENT '優先度',
	`task_phase` VARCHAR(20) NOT NULL DEFAULT '' COMMENT 'タスク進捗',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時 (yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時 (yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--  テーブル futaba_ok2_shippment.t_task_status の構造をダンプしています
CREATE TABLE IF NOT EXISTS `t_task_status` (
  `task_id` int unsigned NOT NULL DEFAULT '0',
  `status` varchar(24) NOT NULL,
  `phase` varchar(24) NOT NULL,
  `robot_id` int unsigned NOT NULL DEFAULT '0',
  `dest_cell` int unsigned NOT NULL DEFAULT '0',
  `task_type` varchar(32) NOT NULL DEFAULT '',
  `instruction` text NOT NULL,
  `updated_date` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`task_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;














-- 1. Progress/State table
-- Use INSERT IGNORE to skip if the line_id (Primary Key) already exists
INSERT IGNORE INTO `t_pallet_supply_status` (line_id, rev)
SELECT line_id, 0 
FROM m_line 
WHERE line_name IN ('T63', 'T64', 'T65');


-- Step B: Insert the 10 empty slots (index 0 to 9)
-- IMPORTANT: pallet_type must be NULL (for INT), not '' (for VARCHAR)
INSERT INTO `t_pallet_supply_pairs` (line_id, pair_index, pallet_type, count)
SELECT m.line_id, n.i, 1, 0 
FROM m_line m
CROSS JOIN (
    SELECT 0 AS i UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 
    UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9
) n
WHERE m.line_name IN ('T63', 'T64', 'T65');











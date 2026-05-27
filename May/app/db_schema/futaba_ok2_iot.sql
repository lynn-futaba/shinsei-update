--
-- Table structure for table `t_input`
--
DROP TABLE IF EXISTS `t_input`;
CREATE TABLE `t_input` (
  `signal_id` INT(8) NOT NULL COMMENT '信号ID',
  `controller` VARCHAR(20) NOT NULL COMMENT 'コントローラー名',
  `item` VARCHAR(20) NOT NULL COMMENT 'アイテム名',
  `array` VARCHAR(20) NOT NULL COMMENT '配列番号',
  `value` VARCHAR(20) NOT NULL COMMENT '値',
  `comment` VARCHAR(20) NOT NULL COMMENT 'コメント',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時(yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時(yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`signal_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `t_output`
--
DROP TABLE IF EXISTS `t_output`;
CREATE TABLE `t_output` (
  `signal_id` INT NOT NULL COMMENT '信号ID',
  `controller` VARCHAR(20) NOT NULL COMMENT 'コントローラー名',
  `item` VARCHAR(20) NOT NULL COMMENT 'アイテム名',
  `array` VARCHAR(20) NOT NULL COMMENT '配列番号',
  `value` VARCHAR(20) NOT NULL COMMENT '値',
  `comment` VARCHAR(20) NOT NULL COMMENT 'コメント',
  `created_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作成日時(yyyy/MM/dd hh:mm:ss)',
  `updated_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新日時(yyyy/MM/dd hh:mm:ss)',
  PRIMARY KEY (`signal_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
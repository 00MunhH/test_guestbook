package com.example.guestbook.config;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.config.server.EnableConfigServer;

/**
 * Spring Cloud Config 서버.
 * 각 서비스의 설정을 중앙에서 제공한다. 여기서는 native(클래스패스/파일) 백엔드를 사용한다.
 * 운영에서는 Git 백엔드(spring.cloud.config.server.git.uri)로 전환 권장.
 */
@EnableConfigServer
@SpringBootApplication
public class ConfigServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(ConfigServerApplication.class, args);
    }
}

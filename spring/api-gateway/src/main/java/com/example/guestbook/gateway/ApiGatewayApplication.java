package com.example.guestbook.gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Spring Cloud Gateway — 모든 외부 요청의 단일 진입점.
 * Eureka에 등록된 서비스로 lb:// 를 통해 라우팅한다.
 */
@SpringBootApplication
public class ApiGatewayApplication {
    public static void main(String[] args) {
        SpringApplication.run(ApiGatewayApplication.class, args);
    }
}

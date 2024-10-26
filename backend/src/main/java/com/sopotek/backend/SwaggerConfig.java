package com.sopotek.backend;

import io.swagger.v3.oas.models.ExternalDocumentation;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.info.License;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class SwaggerConfig {

    @Bean
    public OpenAPI tradeAdvisorOpenAPI() {
        return new OpenAPI()
                .info(new Info().title("Trade Advisor API")
                        .description("API for managing and analyzing trading strategies")
                        .version("v1.0")
                        .contact(new Contact().name("Support Team").email("support@tradeadvisor.org"))
                        .license(new License().name("Apache 2.0").url("https://springdoc.org")))
                .externalDocs(new ExternalDocumentation()
                        .description("Trade Advisor Wiki Documentation")
                        .url("https://tradeadviser.docs.io"));
    }
}

package org.example.core.network

import io.ktor.client.call.body
import io.ktor.client.statement.HttpResponse
import io.ktor.client.statement.bodyAsText
import io.ktor.http.isSuccess
import io.ktor.serialization.JsonConvertException
import io.ktor.serialization.kotlinx.json.DefaultJson
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.onStart
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

abstract class NetworkRepository {


    protected inline fun <reified T, U>(suspend () -> HttpResponse).reduce(
        crossinline block: (T) -> Async<U>
    ) : Flow<Async<U>> {
        return flow {
            val httpResponse = invoke()
            if (httpResponse.status.isSuccess()) {
                val data = httpResponse.body<T>()
                val dataState = block.invoke(data)
                emit(dataState)
            } else {
                val message = try {
                    val json = DefaultJson
                        .parseToJsonElement(httpResponse.bodyAsText())
                        .jsonObject
                    json["message"]?.jsonPrimitive?.content
                } catch (e: Throwable) {
                    e.printStackTrace()
                    httpResponse.bodyAsText()
                }
                val throwable = Throwable(message)
                val state = Async.Failure(throwable)
                emit(state)
            }
        }.onStart {
            emit(Async.Loading)
        }.catch {
            val state = Async.Failure(it)
            emit(state)
        }
    }
}